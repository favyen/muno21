package main

import (
	"../lib"
	"github.com/mitroadmaps/gomapinfer/common"
	"github.com/mitroadmaps/gomapinfer/image"

	"encoding/json"
	"fmt"
	"image/jpeg"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"sync"
)


func main() {
	annotationFname := os.Args[1]
	jpgDir := os.Args[2]
	graphDir := os.Args[3]
	outFname := os.Args[4]

	// Load annotations.
	var annotations []lib.Annotation
	lib.ReadJSONFile(annotationFname, &annotations)

	// Load current labels.
	var labels [][][4]int
	if _, err := os.Stat(outFname); err == nil {
		lib.ReadJSONFile(outFname, &labels)
	}
	for len(labels) < len(annotations) {
		labels = append(labels, nil)
	}

	var curAnnotationIdx int
	for i := range labels {
		if labels[i] != nil {
			curAnnotationIdx = i+1
		}
	}
	curAnnotationIdx = 112

	// Load road network graphs on-demand but cache them permanently.
	graphs := make(map[string]common.GraphGridIndex)
	images := make(map[string][][][3]uint8)
	getGraphAndImage := func(region string, tile [2]int) (common.GraphGridIndex, [][][3]uint8) {
		key := fmt.Sprintf("%s_%d_%d", region, tile[0], tile[1])
		if images[key] != nil {
			return graphs[key], images[key]
		}

		log.Printf("loading graph and image for %s", key)

		graph, err := common.ReadGraph(filepath.Join(graphDir, key+"_2020-07-01_extra.graph"))
		if err != nil {
			panic(err)
		}
		graphs[key] = graph.GridIndex(128)

		for _, year := range []string{"2019", "2018"} {
			fname := filepath.Join(jpgDir, key+"_"+year+".jpg")
			if _, err := os.Stat(fname); os.IsNotExist(err) {
				continue
			}
			images[key] = image.ReadImage(fname)
		}
		if images[key] == nil {
			panic(fmt.Errorf("no image found for %s", key))
		}

		log.Printf("... done!")
		return graphs[key], images[key]
	}

	var mu sync.Mutex

	fileServer := http.FileServer(http.Dir("static/"))
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/" {
			w.Header().Set("Cache-Control", "no-cache")
		}
		fileServer.ServeHTTP(w, r)
	})

	// View the current cluster (_all graph and image, but no labels).
	http.HandleFunc("/view", func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		annotation := annotations[curAnnotationIdx % len(annotations)]
		cluster := annotation.Cluster
		graphIndex, pix := getGraphAndImage(cluster.Region, cluster.Tile)
		mu.Unlock()
		window := lib.ClipPad(cluster.Window, 160, [2]int{len(pix), len(pix[0])})

		crop := image.Crop(pix, window[0], window[1], window[2], window[3])
		rect := common.Rectangle{
			common.Point{float64(window[0]), float64(window[1])},
			common.Point{float64(window[2]), float64(window[3])},
		}
		for _, edge := range graphIndex.Search(rect) {
			segment := edge.Segment()
			sx := int(segment.Start.X) - window[0]
			sy := int(segment.Start.Y) - window[1]
			ex := int(segment.End.X) - window[0]
			ey := int(segment.End.Y) - window[1]
			width := 1
			for _, p := range common.DrawLineOnCells(sx, sy, ex, ey, len(crop), len(crop[0])) {
				for i := -width; i <= width; i++ {
					for j := -width; j <= width; j++ {
						x := p[0]+i
						y := p[1]+j
						if x < 0 || x >= len(crop) || y < 0 || y >= len(crop[x]) {
							continue
						}
						crop[x][y] = [3]uint8{255, 0, 0}
					}
				}
			}
		}

		w.Header().Set("Content-Type", "image/jpeg")
		im := image.AsImage(crop)
		jpeg.Encode(w, im, nil)
	})

	// Get the labels for the current cluster.
	// This way the front-end can render the current labels.
	http.HandleFunc("/labels", func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		defer mu.Unlock()
		var response struct {
			Lines [][4]int
			Window [4]int
		}
		response.Lines = labels[curAnnotationIdx % len(annotations)]
		if response.Lines == nil {
			response.Lines = [][4]int{}
		}

		annotation := annotations[curAnnotationIdx % len(annotations)]
		cluster := annotation.Cluster
		_, pix := getGraphAndImage(cluster.Region, cluster.Tile)
		response.Window = lib.ClipPad(cluster.Window, 160, [2]int{len(pix), len(pix[0])})

		jsonResponse(w, response)
	})

	// Submit labels for the current cluster.
	http.HandleFunc("/label", func(w http.ResponseWriter, r *http.Request) {
		r.ParseForm()
		labelsRaw := r.PostForm.Get("labels")
		var lines [][4]int
		if err := json.Unmarshal([]byte(labelsRaw), &lines); err != nil {
			panic(err)
		}

		mu.Lock()
		labels[curAnnotationIdx] = lines
		lib.WriteJSONFile(outFname, labels)
		mu.Unlock()
	})

	http.HandleFunc("/prev", func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		curAnnotationIdx--
		if curAnnotationIdx < 0 {
			curAnnotationIdx = len(annotations)-1
		}
		mu.Unlock()
	})

	http.HandleFunc("/next", func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		curAnnotationIdx++
		mu.Unlock()
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
