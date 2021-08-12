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
	"strings"
	"sync"
)

/*

(1) Shuffle and visualize


*/

const BigPadding = 128
const SmallPadding = 32
const Dilation = 8

func visualize(clusters []lib.Cluster, jpgDir string, graphDir string, outDir string, annotations []lib.Annotation) {
	if len(clusters) == 0 {
		return
	}
	region := clusters[0].Region
	tile := clusters[0].Tile

	label := fmt.Sprintf("%s_%d_%d", region, tile[0], tile[1])

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

	for i, cluster := range clusters {
		log.Printf("[%s] %d/%d", label, i, len(clusters))

		clusterPrefix := filepath.Join(outDir, fmt.Sprintf("%s_%d_", label, i))

		// aerial images
		dims := [2]int{len(ims[0].Image), len(ims[0].Image[0])}
		window := lib.ClipPad(cluster.Window, BigPadding, dims)
		oldIdx := getGraphIndexFromTimestamp(cluster.FirstTimestamp)-1
		newIdx := getGraphIndexFromTimestamp(cluster.LastTimestamp)
		for _, im := range ims {
			summaryIm := image.Crop(im.Image, window[0], window[1], window[2], window[3])
			image.WriteImage(clusterPrefix + fmt.Sprintf("%s.jpg", im.Timestamp), summaryIm)
		}

		// map images
		baseIm := image.MakeImage(window[2]-window[0], window[3]-window[1], [3]uint8{255, 255, 255})
		gtIm := image.MakeImage(window[2]-window[0], window[3]-window[1], [3]uint8{255, 255, 255})
		rect := common.Rectangle{
			common.Point{float64(window[0]), float64(window[1])},
			common.Point{float64(window[2]), float64(window[3])},
		}
		oldEdges := graphs[oldIdx].WithoutAll.Search(rect)
		newEdges := graphs[newIdx].WithoutAll.Search(rect)
		allEdges := graphs[newIdx].WithAll.Search(rect)

		dims = [2]int{len(baseIm), len(baseIm[0])}
		baseDilate := image.MakeGrayImage(dims[0], dims[1], 0)
		allDilate := image.MakeGrayImage(dims[0], dims[1], 0)
		basePix := image.MakeGrayImage(dims[0], dims[1], 0)
		newPix := image.MakeGrayImage(dims[0], dims[1], 0)
		allPix := image.MakeGrayImage(dims[0], dims[1], 0)
		drawGrayGraph := func(im [][]uint8, edges []*common.Edge) {
			for _, edge := range edges {
				sx := int(edge.Src.Point.X) - window[0]
				sy := int(edge.Src.Point.Y) - window[1]
				ex := int(edge.Dst.Point.X) - window[0]
				ey := int(edge.Dst.Point.Y) - window[1]
				for _, p := range common.DrawLineOnCells(sx, sy, ex, ey, dims[0], dims[1]) {
					im[p[0]][p[1]] = 255
				}
			}
		}
		drawGrayGraph(baseDilate, oldEdges)
		drawGrayGraph(allDilate, allEdges)
		drawGrayGraph(basePix, oldEdges)
		drawGrayGraph(newPix, newEdges)
		drawGrayGraph(allPix, allEdges)
		lib.Dilate(baseDilate, Dilation)
		lib.Dilate(allDilate, Dilation)

		for i := 0; i < dims[0]; i++ {
			for j := 0; j < dims[1]; j++ {
				// base image
				if basePix[i][j] == 255 {
					if allDilate[i][j] == 0 {
						image.DrawRect(baseIm, i, j, 2, [3]uint8{230, 0, 0})
					} else {
						image.DrawRect(baseIm, i, j, 2, [3]uint8{0, 0, 0})
					}
				}

				// gt image
				if newPix[i][j] == 255 {
					if baseDilate[i][j] == 255 {
						image.DrawRect(gtIm, i, j, 2, [3]uint8{0, 0, 0})
					} else {
						image.DrawRect(gtIm, i, j, 2, [3]uint8{0, 230, 0})
					}
				}
			}
		}

		image.WriteImage(clusterPrefix + "base.png", baseIm)
		image.WriteImage(clusterPrefix + "gt.png", gtIm)
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
