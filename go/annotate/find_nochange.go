package main

// Find large windows without any change.

import (
	"github.com/favyen/muno21/go/lib"
	"github.com/mitroadmaps/gomapinfer/common"

	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"math/rand"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

const Dilation int = 8

// orig and newg should both be maps with no service/parking roads
// dims: from sizes.json
// We look for regions where all newg roads are present in oldg and all oldg roads are present in newg.
func process(orig *common.Graph, newg *common.Graph, dims [2]int) [][4]int {
	log.Printf("... draw")
	origPix := make([][]bool, dims[0])
	newPix := make([][]bool, dims[0])
	origDilate := make([][]uint8, dims[0])
	newDilate := make([][]uint8, dims[0])
	bad := make([][]bool, dims[0])
	for i := range origPix {
		origPix[i] = make([]bool, dims[1])
		newPix[i] = make([]bool, dims[1])
		origDilate[i] = make([]uint8, dims[1])
		newDilate[i] = make([]uint8, dims[1])
		bad[i] = make([]bool, dims[1])
	}
	for _, edge := range orig.Edges {
		sx := int(edge.Src.Point.X)
		sy := int(edge.Src.Point.Y)
		ex := int(edge.Dst.Point.X)
		ey := int(edge.Dst.Point.Y)
		for _, p := range common.DrawLineOnCells(sx, sy, ex, ey, dims[0], dims[1]) {
			origPix[p[0]][p[1]] = true
			origDilate[p[0]][p[1]] = 255
		}
	}
	for _, edge := range newg.Edges {
		sx := int(edge.Src.Point.X)
		sy := int(edge.Src.Point.Y)
		ex := int(edge.Dst.Point.X)
		ey := int(edge.Dst.Point.Y)
		for _, p := range common.DrawLineOnCells(sx, sy, ex, ey, dims[0], dims[1]) {
			newPix[p[0]][p[1]] = true
			newDilate[p[0]][p[1]] = 255
		}
	}
	log.Printf("... dilate")
	lib.Dilate(origDilate, Dilation)
	lib.Dilate(newDilate, Dilation)

	log.Printf("... compute bad")
	for i := range bad {
		for j := range bad[i] {
			if newPix[i][j] && origDilate[i][j] == 0 {
				bad[i][j] = true
			}
			if origPix[i][j] && newDilate[i][j] == 0 {
				bad[i][j] = true
			}
		}
	}

	log.Printf("... get rectangles")
	rects := lib.MaximalRectangles(bad, 512)

	for _, rect := range rects {
		for i := rect[0]; i < rect[2]; i++ {
			for j := rect[1]; j < rect[3]; j++ {
				if bad[i][j] {
					panic(fmt.Errorf("bad rect"))
				}
			}
		}
	}

	log.Printf("... tighten rectangles")
	var tightRects [][4]int
	for _, rect := range rects {
		// tighten the rectangle by removing padding that isn't set in newPix

		// (1) remove rows from top/bottom
		for rect[1] < rect[3] {
			ok1 := false
			ok2 := false
			for i := rect[0]; i < rect[2]; i++ {
				if newPix[i][rect[1]] {
					ok1 = true
				}
				if newPix[i][rect[3]-1] {
					ok2 = true
				}
			}
			if ok1 && ok2 {
				break
			}
			if !ok1 {
				rect[1]++
			}
			if !ok2 {
				rect[3]--
			}
		}
		// (2) remove cols from left/right
		for rect[0] < rect[2] {
			ok1 := false
			ok2 := false
			for i := rect[1]; i < rect[3]; i++ {
				if newPix[rect[0]][i] {
					ok1 = true
				}
				if newPix[rect[2]-1][i] {
					ok2 = true
				}
			}
			if ok1 && ok2 {
				break
			}
			if !ok1 {
				rect[0]++
			}
			if !ok2 {
				rect[2]--
			}
		}

		if rect[2]-rect[0] < 512 || rect[3]-rect[1] < 512 {
			continue
		}

		if rect[2]-rect[0] > 1024 {
			rect[2] = rect[0]+1024
		}
		if rect[3]-rect[1] > 1024 {
			rect[3] = rect[1]+1024
		}

		tightRects = append(tightRects, rect)
	}

	log.Println(len(tightRects))
	return tightRects
}

func main() {
	graphDir := os.Args[1]
	outDir := os.Args[2]

	// load all graphs
	files, err := ioutil.ReadDir(graphDir)
	if err != nil {
		panic(err)
	}
	type TileKey struct {
		Region string
		Tile [2]int
	}
	type GraphItem struct {
		WithoutAll *common.Graph
		WithAll *common.Graph
		Timestamp string
	}
	// list of timestamps where graphs are available in the tile
	graphsByTile := make(map[TileKey][]string)
	for _, fi := range files {
		if !strings.HasSuffix(fi.Name(), "_all.graph") {
			continue
		}
		label := strings.Split(fi.Name(), "_all.graph")[0]
		parts := strings.Split(label, "_")
		region := parts[0]
		x, _ := strconv.Atoi(parts[1])
		y, _ := strconv.Atoi(parts[2])
		timestamp := parts[3]

		/*if region != "atlanta" {
			continue
		}*/

		if timestamp != "2013-07-01" && timestamp != "2020-07-01" {
			continue
		}

		tileKey := TileKey{
			Region: region,
			Tile: [2]int{x, y},
		}
		graphsByTile[tileKey] = append(graphsByTile[tileKey], timestamp)
	}

	// load tile sizes
	var rawSizes map[string][2]int
	bytes, err := ioutil.ReadFile("sizes.json")
	if err != nil {
		panic(err)
	}
	if err := json.Unmarshal(bytes, &rawSizes); err != nil {
		panic(err)
	}
	sizes := make(map[TileKey][2]int)
	for label, dims := range rawSizes {
		parts := strings.Split(label, "_")
		region := parts[0]
		x, _ := strconv.Atoi(parts[1])
		y, _ := strconv.Atoi(parts[2])
		sizes[TileKey{region, [2]int{x, y}}] = dims
	}

	for tileKey, timestamps := range graphsByTile {
		outFname := filepath.Join(outDir, fmt.Sprintf("%s_%d_%d.json", tileKey.Region, tileKey.Tile[0], tileKey.Tile[1]))
		if _, err := os.Stat(outFname); err == nil {
			continue
		}

		sort.Strings(timestamps)
		var items []GraphItem
		for _, timestamp := range timestamps {
			label := fmt.Sprintf("%s_%d_%d_%s", tileKey.Region, tileKey.Tile[0], tileKey.Tile[1], timestamp)
			log.Printf("loading %s", label)

			g1, err := common.ReadGraph(filepath.Join(graphDir, label+".graph"))
			if err != nil {
				panic(err)
			}
			g2, err := common.ReadGraph(filepath.Join(graphDir, label+"_all.graph"))
			if err != nil {
				panic(err)
			}
			items = append(items, GraphItem{
				WithoutAll: g1,
				WithAll: g2,
				Timestamp: timestamp,
			})
		}

		dims := sizes[tileKey]
		var clusters []lib.Cluster

		for i := 1; i < len(items); i++ {
			prevItem := items[i-1]
			nextItem := items[i]
			log.Printf("processing at tile %s[%d, %d]: timestamps %s and %s", tileKey.Region, tileKey.Tile[0], tileKey.Tile[1], prevItem.Timestamp, nextItem.Timestamp)
			rects := process(prevItem.WithoutAll, nextItem.WithoutAll, dims)
			log.Printf("... found %d rectangles", len(rects))

			if len(rects) > 20 {
				var sampleRects [][4]int
				for _, idx := range rand.Perm(len(rects))[0:20] {
					sampleRects = append(sampleRects, rects[idx])
				}
				rects = sampleRects
			}

			for _, rect := range rects {
				cr := lib.ChangedRoad{}
				cr.Region = tileKey.Region
				cr.Tile = tileKey.Tile
				cr.OrigTimestamp = nextItem.Timestamp
				cr.NewTimestamp = prevItem.Timestamp
				cluster := lib.Cluster{
					Region: tileKey.Region,
					Tile: tileKey.Tile,
					FirstTimestamp: nextItem.Timestamp,
					LastTimestamp: nextItem.Timestamp,
					Window: [4]int{rect[0]+128, rect[1]+128, rect[2]-128, rect[3]-128},
					Size: 0,
				}
				clusters = append(clusters, cluster)
			}
		}

		bytes, err = json.Marshal(clusters)
		if err != nil {
			panic(err)
		}
		if err := ioutil.WriteFile(outFname, bytes, 0644); err != nil {
			panic(err)
		}
	}
}
