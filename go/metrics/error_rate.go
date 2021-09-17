package main

// Find large windows without any change.

import (
	"github.com/favyen/muno21/go/lib"
	"github.com/mitroadmaps/gomapinfer/common"

	"fmt"
	"log"
	"os"
	"path/filepath"
)

const Dilation int = 16
const Padding int = 0

func getPixAndDilated(graph *common.Graph, window [4]int) ([][]bool, [][]uint8) {
	dims := [2]int{
		window[2]-window[0],
		window[3]-window[1],
	}
	pix := make([][]bool, dims[0])
	dilate := make([][]uint8, dims[0])
	for i := range pix {
		pix[i] = make([]bool, dims[1])
		dilate[i] = make([]uint8, dims[1])
	}
	for _, edge := range graph.Edges {
		sx := int(edge.Src.Point.X) - window[0]
		sy := int(edge.Src.Point.Y) - window[1]
		ex := int(edge.Dst.Point.X) - window[0]
		ey := int(edge.Dst.Point.Y) - window[1]
		for _, p := range common.DrawLineOnCells(sx, sy, ex, ey, dims[0], dims[1]) {
			pix[p[0]][p[1]] = true
			dilate[p[0]][p[1]] = 255
		}
	}
	lib.Dilate(dilate, Dilation)
	return pix, dilate
}

// Make sure that newg contains no road segments that are further than Dilation from orig.
// And vice versa (in case map update method deletes a road incorrectly).
func isError(orig *common.Graph, newg *common.Graph, extra *common.Graph, window [4]int) bool {
	origPix, origDilate := getPixAndDilated(orig, window)
	newPix, newDilate := getPixAndDilated(newg, window)
	_, extraDilate := getPixAndDilated(extra, window)

	for i := range newPix {
		for j := range newPix[i] {
			if newPix[i][j] && extraDilate[i][j] == 0 && origDilate[i][j] == 0 {
				return true
			}
			if origPix[i][j] && newDilate[i][j] == 0 {
				return true
			}
		}
	}

	return false
}

const BaseGraphSuffix = "_2013-07-01.graph"
const ExtraGraphSuffix = "_2020-07-01_extra.graph"

func main() {
	annotationFname := os.Args[1]
	inferredDir := os.Args[2]
	graphDir := os.Args[3]
	testFname := os.Args[4]

	var annotations []lib.Annotation
	lib.ReadJSONFile(annotationFname, &annotations)

	var testRegions []string
	lib.ReadJSONFile(testFname, &testRegions)
	testSet := make(map[string]bool)
	for _, region := range testRegions {
		testSet[region] = true
	}

	// group annotations by tiles
	type TileKey struct {
		Region string
		Tile [2]int
	}
	type Item struct {
		Annotation lib.Annotation
		Index int
	}
	groups := make(map[TileKey][]Item)
	for idx, annotation := range annotations {
		if !annotation.HasTag("nochange") || !testSet[annotation.Cluster.Region] {
			continue
		}
		k := TileKey{annotation.Cluster.Region, annotation.Cluster.Tile}
		groups[k] = append(groups[k], Item{annotation, idx})
	}

	processTile := func(k TileKey, items []Item) (int, int) {
		label := fmt.Sprintf("%s_%d_%d", k.Region, k.Tile[0], k.Tile[1])
		baseg := lib.ReadGraph(filepath.Join(graphDir, label+BaseGraphSuffix))
		baseIndex := baseg.GridIndex(128)
		extrag := lib.ReadGraph(filepath.Join(graphDir, label+ExtraGraphSuffix))
		extraIndex := extrag.GridIndex(128)

		var count, errors int
		for _, item := range items {
			annot := item.Annotation
			cluster := annot.Cluster
			window := [4]int{
				cluster.Window[0]-Padding,
				cluster.Window[1]-Padding,
				cluster.Window[2]+Padding,
				cluster.Window[3]+Padding,
			}
			bigRect := common.Rectangle{
				common.Point{float64(window[0]-64), float64(window[1]-64)},
				common.Point{float64(window[2]+64), float64(window[3]+64)},
			}
			inferredg := lib.ReadGraph(filepath.Join(inferredDir, fmt.Sprintf("%d.graph", item.Index)))
			baseSubgraph := common.GraphFromEdges(baseIndex.Search(bigRect))
			extraSubgraph := common.GraphFromEdges(extraIndex.Search(bigRect))

			count++
			if isError(baseSubgraph, inferredg, extraSubgraph, window) {
				//log.Println(item.Index)
				errors++
			}
		}
		return count, errors
	}

	type Task struct {
		Key TileKey
		Items []Item
	}
	ch := make(chan Task)
	donech := make(chan [2]int)
	for i := 0; i < 24; i++ {
		go func() {
			var count, errors int
			for task := range ch {
				curCount, curErrors := processTile(task.Key, task.Items)
				count += curCount
				errors += curErrors
			}
			donech <- [2]int{count, errors}
		}()
	}
	for key, items := range groups {
		ch <- Task{key, items}
	}
	close(ch)
	var count, errors int
	for i := 0; i < 24; i++ {
		res := <- donech
		count += res[0]
		errors += res[1]
	}
	rate := float64(errors)/float64(count)
	log.Println("error_rate =", rate)

	outFname := filepath.Join(inferredDir, "error.json")
	lib.WriteJSONFile(outFname, rate)
}
