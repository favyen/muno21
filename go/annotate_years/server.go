package main

import (
	"github.com/favyen/muno21/go/lib"
	"github.com/mitroadmaps/gomapinfer/common"
	"github.com/mitroadmaps/gomapinfer/image"

	"encoding/json"
	"fmt"
	"image/jpeg"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"sync"
)

type Label struct {
	// True if the road was constructed, false if it was bulldozed.
	Constructed bool
	// Years when the activity started and ended.
	Start int
	End int
	// Segments that were constructed or bulldozed.
	Segments []common.Segment
	// Set if only a part of this road was under construction.
	Partial bool
}

func main() {
	annotationFname := os.Args[1]
	jpgDir := os.Args[2]
	graphDir := os.Args[3]
	outFname := os.Args[4]

	// Load annotations.
	var annotations []lib.Annotation
	lib.ReadJSONFile(annotationFname, &annotations)

	// Load current labels.
	var labels [][]Label
	if _, err := os.Stat(outFname); err == nil {
		lib.ReadJSONFile(outFname, &labels)
	}

	// Load road network graphs and images on-demand but cache them permanently.
	baseGraphs := make(map[string]common.GraphGridIndex)
	gtGraphs := make(map[string]common.GraphGridIndex)
	images := make(map[string]map[int][][][3]uint8)
	getGraphsAndImages := func(region string, tile [2]int) (baseIndex common.GraphGridIndex, gtIndex common.GraphGridIndex, ims map[int][][][3]uint8) {
		key := fmt.Sprintf("%s_%d_%d", region, tile[0], tile[1])
		if images[key] != nil {
			return baseGraphs[key], gtGraphs[key], images[key]
		}

		log.Printf("loading graph and images for %s", key)
		getGraphIndex := func(suffix string) common.GraphGridIndex {
			graph, err := common.ReadGraph(filepath.Join(graphDir, key+suffix))
			if err != nil {
				panic(err)
			}
			return graph.GridIndex(128)
		}
		baseGraphs[key] = getGraphIndex("_2013-07-01.graph")
		gtGraphs[key] = getGraphIndex("_2020-07-01.graph")

		images[key] = make(map[int][][][3]uint8)
		var mu sync.Mutex
		var wg sync.WaitGroup
		for year := 2012; year <= 2019; year++ {
			fname := filepath.Join(jpgDir, fmt.Sprintf("%s_%d.jpg", key, year))
			if _, err := os.Stat(fname); os.IsNotExist(err) {
				continue
			}
			log.Printf("... %d", year)
			wg.Add(1)
			go func(year int, fname string) {
				defer wg.Done()
				im := image.ReadImage(fname)
				mu.Lock()
				images[key][year] = im
				mu.Unlock()
			}(year, fname)
		}
		wg.Wait()

		log.Printf("... done!")
		return baseGraphs[key], gtGraphs[key], images[key]
	}

	var mu sync.Mutex

	// Label structs with Constructed and Segment set but Start/End/Partial need to be annotated
	var labelQueue []Label
	// Annotated labels that should be added to labels once we advance to the next thing.
	var pendingLabels []Label
	// Current stuff we're working with.
	var curData struct {
		Index int
		Annotation lib.Annotation
		Window [4]int
		Images map[int][][][3]uint8
		Base *common.Graph
		Gt *common.Graph
	}

	// Get current years of images based on curData.Images.
	// Returned array is sorted.
	getYears := func() []int {
		var years []int
		for year := range curData.Images {
			years = append(years, year)
		}
		sort.Ints(years)
		return years
	}

	// Called to move on to next annotation whenever labelQueue is empty.
	// Caller must have the lock.
	loadCur := func() {
		// Find first annotation where we don't have labels yet, and annotation has custom years.
		curData.Index = len(labels)
		for annotations[curData.Index].Years == [2]int{0, 0} {
			curData.Index++
		}

		curData.Annotation = annotations[curData.Index]
		cluster := curData.Annotation.Cluster
		baseIndex, gtIndex, ims := getGraphsAndImages(cluster.Region, cluster.Tile)

		var exampleIm [][][3]uint8
		for _, im := range ims {
			exampleIm = im
			break
		}

		curData.Window = lib.ClipPad(cluster.Window, 64, [2]int{len(exampleIm), len(exampleIm[0])})
		curData.Images = make(map[int][][][3]uint8)
		for year, im := range ims {
			curData.Images[year] = image.Crop(im, curData.Window[0], curData.Window[1], curData.Window[2], curData.Window[3])
		}

		rect := common.Rectangle{
			common.Point{float64(curData.Window[0]), float64(curData.Window[1])},
			common.Point{float64(curData.Window[2]), float64(curData.Window[3])},
		}
		curData.Base = GraphFromEdges(baseIndex.Search(rect))
		curData.Gt = GraphFromEdges(gtIndex.Search(rect))

		// Load each connected component of changed roads into a Label.
		labelQueue = []Label{}
		pendingLabels = []Label{}
		for _, changedRoad := range cluster.Changes {
			var label Label
			label.Constructed = !changedRoad.Deleted
			label.Segments = changedRoad.Segments
			labelQueue = append(labelQueue, label)
		}
	}
	loadCur()

	fileServer := http.FileServer(http.Dir("static/"))
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/" {
			w.Header().Set("Cache-Control", "no-cache")
		}
		fileServer.ServeHTTP(w, r)
	})

	// View one of the background images.
	http.HandleFunc("/view_image", func(w http.ResponseWriter, r *http.Request) {
		r.ParseForm()
		year, _ := strconv.Atoi(r.Form.Get("year"))
		mu.Lock()
		im := curData.Images[year]

		// Ensure im is a copy.
		im = image.Crop(im, 0, 0, len(im), len(im[0]))

		curLabel := labelQueue[0]
		for _, segment := range curLabel.Segments {
			sx := int(segment.Start.X) - curData.Window[0]
			sy := int(segment.Start.Y) - curData.Window[1]
			ex := int(segment.End.X) - curData.Window[0]
			ey := int(segment.End.Y) - curData.Window[1]
			for _, p := range common.DrawLineOnCells(sx, sy, ex, ey, len(im), len(im[0])) {
				im[p[0]][p[1]] = [3]uint8{255, 0, 0}
			}
		}
		mu.Unlock()
		w.Header().Set("Content-Type", "image/jpeg")
		jpeg.Encode(w, image.AsImage(im), nil)
	})

	// View visualization of the current labels.
	http.HandleFunc("/view_vis", func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		years := getYears()
		curLabel := labelQueue[0]

		// Background image for visualization is last year if curLabel.Constructed, or first year otherwise.
		var im [][][3]uint8
		if curLabel.Constructed {
			im = curData.Images[years[len(years)-1]]
		} else {
			im = curData.Images[years[0]]
		}
		// Ensure im is a copy.
		im = image.Crop(im, 0, 0, len(im), len(im[0]))

		for _, segment := range curLabel.Segments {
			sx := int(segment.Start.X) - curData.Window[0]
			sy := int(segment.Start.Y) - curData.Window[1]
			ex := int(segment.End.X) - curData.Window[0]
			ey := int(segment.End.Y) - curData.Window[1]
			width := 1
			for _, p := range common.DrawLineOnCells(sx, sy, ex, ey, len(im), len(im[0])) {
				for i := -width; i <= width; i++ {
					for j := -width; j <= width; j++ {
						x := p[0]+i
						y := p[1]+j
						if x < 0 || x >= len(im) || y < 0 || y >= len(im[x]) {
							continue
						}
						im[x][y] = [3]uint8{255, 0, 0}
					}
				}
			}
		}
		mu.Unlock()

		w.Header().Set("Content-Type", "image/jpeg")
		jpeg.Encode(w, image.AsImage(im), nil)
	})

	// Get metadata for the current label.
	http.HandleFunc("/meta", func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		var response struct {
			Window [4]int
			Years []int
		}
		response.Window = curData.Window
		response.Years = getYears()
		mu.Unlock()

		jsonResponse(w, response)
	})

	// Split current label into one label per road segment.
	http.HandleFunc("/split", func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		defer mu.Unlock()
		curLabel := labelQueue[0]
		var newLabels []Label

		// First construct a graph from the segments in the label.
		g := &common.Graph{}
		nodemap := make(map[[2]int]*common.Node)
		for _, segment := range curLabel.Segments {
			srcpos := [2]int{int(segment.Start.X), int(segment.Start.Y)}
			dstpos := [2]int{int(segment.End.X), int(segment.End.Y)}
			if nodemap[srcpos] == nil {
				nodemap[srcpos] = g.AddNode(segment.Start)
			}
			if nodemap[dstpos] == nil {
				nodemap[dstpos] = g.AddNode(segment.End)
			}
			g.AddBidirectionalEdge(nodemap[srcpos], nodemap[dstpos])
		}

		// Now split.
		roadSegments := g.GetRoadSegments()
		seenRS := make(map[[3]int]bool)
		for _, rs := range roadSegments {
			seenKey1 := [3]int{rs.Edges[0].Src.ID, rs.Edges[0].Dst.ID, rs.Edges[len(rs.Edges)-1].Dst.ID}
			seenKey2 := [3]int{rs.Edges[len(rs.Edges)-1].Dst.ID, rs.Edges[len(rs.Edges)-1].Src.ID, rs.Edges[0].Src.ID}
			if seenRS[seenKey1] || seenRS[seenKey2] {
				continue
			}
			seenRS[seenKey1] = true
			seenRS[seenKey2] = true

			label := curLabel
			var segments []common.Segment
			for _, edge := range rs.Edges {
				segments = append(segments, edge.Segment())
			}
			label.Segments = segments
			newLabels = append(newLabels, label)
		}
		labelQueue = append(newLabels, labelQueue[1:]...)
	})

	// Extend the current label with an additional road segment.
	http.HandleFunc("/extend", func(w http.ResponseWriter, r *http.Request) {
		r.ParseForm()
		x, _ := strconv.Atoi(r.Form.Get("x"))
		y, _ := strconv.Atoi(r.Form.Get("y"))

		mu.Lock()
		defer mu.Unlock()
		curLabel := labelQueue[0]

		var graph *common.Graph
		if curLabel.Constructed {
			graph = curData.Gt
		} else {
			graph = curData.Base
		}

		// Find closest road segment to this point.
		// First, find closest edge, then map that to the corresponding road segment.
		var closestEdge *common.Edge
		var closestDistance float64
		for _, edge := range graph.Edges {
			d := edge.Segment().Distance(common.Point{float64(x), float64(y)})
			if closestEdge == nil || d < closestDistance {
				closestEdge = edge
				closestDistance = d
			}
		}
		_, edgeToSegment, _ := graph.GetRoadSegmentGraph()
		rs := edgeToSegment[closestEdge.ID]
		for _, edge := range rs.Edges {
			curLabel.Segments = append(curLabel.Segments, edge.Segment())
		}
	})

	http.HandleFunc("/submit", func(w http.ResponseWriter, r *http.Request) {
		r.ParseForm()
		start, _ := strconv.Atoi(r.PostForm.Get("start"))
		end, _ := strconv.Atoi(r.PostForm.Get("end"))
		partial := r.PostForm.Get("partial") == "yes"

		mu.Lock()
		defer mu.Unlock()
		curLabel := labelQueue[0]
		labelQueue = labelQueue[1:]
		curLabel.Start = start
		curLabel.End = end
		curLabel.Partial = partial
		pendingLabels = append(pendingLabels, curLabel)

		if len(labelQueue) == 0 {
			// Incorporate the pending labels and write all the labels.
			for len(labels) <= curData.Index {
				labels = append(labels, nil)
			}
			labels[curData.Index] = pendingLabels
			lib.WriteJSONFile(outFname, labels)

			// Move on to the next annotation.
			loadCur()
		}
	})

	log.Printf("starting on :8080")
	log.Fatal(http.ListenAndServe(":8080", nil))
}

func jsonResponse(w http.ResponseWriter, x interface{}) {
	bytes, err := json.Marshal(x)
	if err != nil {
		panic(err)
	}
	w.Header().Set("Content-Type", "application/json")
	w.Write(bytes)
}

func GraphFromEdges(edges []*common.Edge) *common.Graph {
	g := &common.Graph{}
	nodemap := make(map[int]*common.Node)
	for _, edge := range edges {
		if nodemap[edge.Src.ID] == nil {
			nodemap[edge.Src.ID] = g.AddNode(edge.Src.Point)
		}
		if nodemap[edge.Dst.ID] == nil {
			nodemap[edge.Dst.ID] = g.AddNode(edge.Dst.Point)
		}
		g.AddEdge(nodemap[edge.Src.ID], nodemap[edge.Dst.ID])
	}
	return g
}
