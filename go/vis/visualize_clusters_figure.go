package main

import (
	"../lib"
	"github.com/mitroadmaps/gomapinfer/common"
	"github.com/mitroadmaps/gomapinfer/image"

	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
)

const BigPadding = 128
const SmallPadding = 32

func visualize(clusters []lib.Cluster, jpgDir string, graphDir string, outDir string, annotations []lib.Annotation) {
	if len(clusters) == 0 {
		return
	}
	region := clusters[0].Region
	tile := clusters[0].Tile

	label := fmt.Sprintf("%s_%d_%d", region, tile[0], tile[1])
	myDir := filepath.Join(outDir, label)
	if err := os.MkdirAll(myDir, 0755); err != nil {
		panic(err)
	}

	// load images
	log.Printf("[%s] loading images", label)
	type Image struct {
		Timestamp string
		Image [][][3]uint8
	}
	var ims []Image
	files, err := ioutil.ReadDir(jpgDir)
	if err != nil {
		panic(err)
	}
	for _, fi := range files {
		if !strings.HasSuffix(fi.Name(), ".jpg") {
			continue
		}
		if !strings.HasPrefix(fi.Name(), label+"_") {
			continue
		}
		timestamp := strings.Split(strings.Split(fi.Name(), ".jpg")[0], label+"_")[1]
		if timestamp != "2012" && timestamp != "2013" && timestamp != "2018" && timestamp != "2019" {
			continue
		}
		im := image.ReadImage(filepath.Join(jpgDir, fi.Name()))
		ims = append(ims, Image{
			Timestamp: timestamp,
			Image: im,
		})
	}
	sort.Slice(ims, func(i, j int) bool {
		return ims[i].Timestamp < ims[j].Timestamp
	})

	// load graphs
	log.Printf("[%s] loading graphs", label)
	type Graph struct {
		Timestamp string
		WithoutAll common.GraphGridIndex
		WithAll common.GraphGridIndex
	}
	var graphs []Graph
	files, err = ioutil.ReadDir(graphDir)
	if err != nil {
		panic(err)
	}
	for _, fi := range files {
		if !strings.HasSuffix(fi.Name(), "_all.graph") {
			continue
		}
		if !strings.HasPrefix(fi.Name(), label+"_") {
			continue
		}
		timestamp := strings.Split(strings.Split(fi.Name(), "_all.graph")[0], label+"_")[1]
		if timestamp != "2013-07-01" && timestamp != "2020-07-01" {
			continue
		}
		g1, err := common.ReadGraph(filepath.Join(graphDir, label+"_"+timestamp+".graph"))
		if err != nil {
			panic(err)
		}
		g2, err := common.ReadGraph(filepath.Join(graphDir, label+"_"+timestamp+"_all.graph"))
		if err != nil {
			panic(err)
		}
		graphs = append(graphs, Graph{
			Timestamp: timestamp,
			WithoutAll: g1.GridIndex(128),
			WithAll: g2.GridIndex(128),
		})
	}
	sort.Slice(graphs, func(i, j int) bool {
		return graphs[i].Timestamp < graphs[j].Timestamp
	})
	getGraphIndexFromTimestamp := func(timestamp string) int {
		for i, g := range graphs {
			if g.Timestamp == timestamp {
				return i
			}
		}
		return -1
	}

	drawSegment := func(im [][][3]uint8, offset [2]int, segment common.Segment, color [3]uint8, width int) {
		sx := int(segment.Start.X) - offset[0]
		sy := int(segment.Start.Y) - offset[1]
		ex := int(segment.End.X) - offset[0]
		ey := int(segment.End.Y) - offset[1]
		for _, p := range common.DrawLineOnCells(sx, sy, ex, ey, len(im), len(im[0])) {
			for i := -width; i <= width; i++ {
				for j := -width; j <= width; j++ {
					x := p[0]+i
					y := p[1]+j
					if x < 0 || x >= len(im) || y < 0 || y >= len(im[x]) {
						continue
					}
					im[x][y] = color
				}
			}
		}
	}

	clipPad := func(rect [4]int, padding int, dims [2]int) [4]int {
		rect = [4]int{
			rect[0]-padding,
			rect[1]-padding,
			rect[2]+padding,
			rect[3]+padding,
		}
		if rect[0] < 0 {
			rect[0] = 0
		}
		if rect[1] < 0 {
			rect[1] = 0
		}
		if rect[2] >= dims[0] {
			rect[2] = dims[0]-1
		}
		if rect[3] >= dims[1] {
			rect[3] = dims[1]-1
		}
		return rect
	}

	for i, cluster := range clusters {
		log.Printf("[%s] %d/%d", label, i, len(clusters))

		clusterDir := filepath.Join(myDir, strconv.Itoa(i))
		os.MkdirAll(clusterDir, 0755)

		// for summary image
		drawCluster := func(im [][][3]uint8, offset [2]int, oldIdx int, newIdx int) {
			// draw the old graph in blue
			rect := common.Rectangle{
				common.Point{float64(offset[0]), float64(offset[1])},
				common.Point{float64(offset[0]+len(im)), float64(offset[1]+len(im[0]))},
			}
			for _, edge := range graphs[oldIdx].WithoutAll.Search(rect) {
				segment := edge.Segment()
				drawSegment(im, offset, segment, [3]uint8{0, 0, 0}, 2)
			}

			// highlight the changes with wide lines
			for _, change := range cluster.Changes {
				var color [3]uint8
				if change.Deleted {
					color = [3]uint8{230, 0, 0}
				} else {
					color = [3]uint8{0, 230, 0}
				}
				for _, segment := range change.Segments {
					drawSegment(im, offset, segment, color, 2)
				}
			}
		}

		// write summary image
		dims := [2]int{len(ims[0].Image), len(ims[0].Image[0])}
		summaryRect := clipPad(cluster.Window, BigPadding, dims)
		oldIdx := getGraphIndexFromTimestamp(cluster.FirstTimestamp)-1
		newIdx := getGraphIndexFromTimestamp(cluster.LastTimestamp)
		for _, im := range ims {
			summaryIm := image.Crop(im.Image, summaryRect[0], summaryRect[1], summaryRect[2], summaryRect[3])
			image.WriteImage(filepath.Join(clusterDir, fmt.Sprintf("summary_%s.jpg", im.Timestamp)), summaryIm)
		}
		summaryIm := image.MakeImage(summaryRect[2]-summaryRect[0], summaryRect[3]-summaryRect[1], [3]uint8{255, 255, 255})
		drawCluster(summaryIm, [2]int{summaryRect[0], summaryRect[1]}, oldIdx, newIdx)
		image.WriteImage(filepath.Join(clusterDir, "road.png"), summaryIm)
	}

	html := `
<html>
<body>
<table>
	<thead>
		<tr>
			<th>#</th>
			<th>Old</th>
			<th>New</th>
			<th>Road Network</th>
			<th>Region</th>
			<th>Years</th>
			<th>Tags</th>
		</tr>
	</thead>
	<tbody>
	`
	for i, cluster := range clusters {
		firstTimestamp := ims[0].Timestamp
		lastTimestamp := ims[len(ims)-1].Timestamp
		region := cluster.Label()
		years := ""
		tags := ""
		if annotations != nil {
			years = fmt.Sprintf("%d-%d", annotations[i].Years[0], annotations[i].Years[1])
			tags = strings.Join(annotations[i].Tags, ", ")
		}
		html += fmt.Sprintf(`
		<tr>
			<td>%d</td>
			<td><img style="max-width:500px" src="%d/summary_%s.jpg"></td>
			<td><img style="max-width:500px" src="%d/summary_%s.jpg"></td>
			<td><img style="max-width:500px" src="%d/road.png"></td>
			<td>%s</td>
			<td>%s</td>
			<td>%s</td>
		</tr>
		`, i, i, firstTimestamp, i, lastTimestamp, i, region, years, tags)
	}
	html += `
	</tbody>
</table>
</body>
</html>`
	if err := ioutil.WriteFile(filepath.Join(myDir, "index.html"), []byte(html), 0644); err != nil {
		panic(err)
	}
}

func main() {
	clusterDir := os.Args[1]
	jpgDir := os.Args[2]
	graphDir := os.Args[3]
	outDir := os.Args[4]

	var annotationFname string
	if len(os.Args) >= 6 {
		annotationFname = os.Args[5]
	}

	var annotations []lib.Annotation
	if annotationFname != "" {
		bytes, err := ioutil.ReadFile(annotationFname)
		if err != nil {
			panic(err)
		}
		if err := json.Unmarshal(bytes, &annotations); err != nil {
			panic(err)
		}
	}

	ch := make(chan string)
	var wg sync.WaitGroup
	for i := 0; i < 16; i++ {
		wg.Add(1)
		go func() {
			for fname := range ch {
				label := strings.Split(fname, ".json")[0]
				var clusters []lib.Cluster
				var curAnnotations []lib.Annotation
				if annotations != nil {
					for _, a := range annotations {
						if a.Cluster.Label() != label {
							continue
						}
						clusters = append(clusters, a.Cluster)
						curAnnotations = append(curAnnotations, a)
					}
				} else {
					bytes, err := ioutil.ReadFile(filepath.Join(clusterDir, fname))
					if err != nil {
						panic(err)
					}
					if err := json.Unmarshal(bytes, &clusters); err != nil {
						panic(err)
					}
				}
				visualize(clusters, jpgDir, graphDir, outDir, curAnnotations)
			}
			wg.Done()
		}()
	}

	files, err := ioutil.ReadDir(clusterDir)
	if err != nil {
		panic(err)
	}
	for _, fi := range files {
		if !strings.HasSuffix(fi.Name(), ".json") {
			continue
		}
		ch <- fi.Name()
	}
	close(ch)
	wg.Wait()
}
