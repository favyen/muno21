package main

// Find roads that changed (were added or removed) between all pairs of consecutive timestamps.

import (
	"./lib"
	"github.com/mitroadmaps/gomapinfer/common"
	//"github.com/mitroadmaps/gomapinfer/image"

	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

func ChangedRoadFromEdges(edges []*common.Edge) lib.ChangedRoad {
	cr := lib.ChangedRoad{}
	for _, edge := range edges {
		cr.EdgeIDs = append(cr.EdgeIDs, edge.ID)
		cr.Segments = append(cr.Segments, edge.Segment())
	}
	return cr
}

const Padding int = 256
const SmallDilation int = 4
const Dilation int = 32
const MinLength float64 = 32
const MinTotalLength float64 = 75

// orig: should be an _all map
// newg: should be a map with no service/parking roads
// dims: from sizes.json
// Returns groups of edges in newg that don't appear in oldg.
func findChange(orig *common.Graph, newg *common.Graph, dims [2]int) [][]*common.Edge {
	// find pixels in the original image where there are roads
	// to do so, we trace each road, and then dilate the image by 5 m on both axes
	origPix := make([][]uint8, dims[0])
	smallPix := make([][]uint8, dims[0])
	for i := range origPix {
		origPix[i] = make([]uint8, dims[1])
		smallPix[i] = make([]uint8, dims[1])
	}
	for _, edge := range orig.Edges {
		sx := int(edge.Src.Point.X)
		sy := int(edge.Src.Point.Y)
		ex := int(edge.Dst.Point.X)
		ey := int(edge.Dst.Point.Y)
		for _, p := range common.DrawLineOnCells(sx, sy, ex, ey, dims[0], dims[1]) {
			origPix[p[0]][p[1]] = 255
			smallPix[p[0]][p[1]] = 255
		}
	}
	lib.Dilate(origPix, Dilation)
	lib.Dilate(smallPix, SmallDilation)

	// for each road segment in newg, see if middle of road segment is not in origPix
	// if so, then it's a changed road
	// then we do BFS to find neighboring segments that are also changed, with smaller threshold
	roadSegments := newg.GetRoadSegments()
	nodeToRS := make(map[int][]common.RoadSegment)
	for _, rs := range roadSegments {
		nodeToRS[rs.Src().ID] = append(nodeToRS[rs.Src().ID], rs)
	}
	seenRS := make(map[[3]int]bool)
	markSeen := func(rs common.RoadSegment) {
		edge1 := rs.Edges[0]
		edge2 := rs.Edges[len(rs.Edges)-1]
		seenRS[[3]int{edge1.Src.ID, edge1.Dst.ID, edge2.Dst.ID}] = true
		seenRS[[3]int{edge2.Dst.ID, edge2.Src.ID, edge1.Src.ID}] = true
	}
	isSeen := func(rs common.RoadSegment) bool {
		edge1 := rs.Edges[0]
		edge2 := rs.Edges[len(rs.Edges)-1]
		return seenRS[[3]int{edge1.Src.ID, edge1.Dst.ID, edge2.Dst.ID}]
	}
	var groups [][]*common.Edge
	for _, baseRS := range roadSegments {
		if isSeen(baseRS) {
			continue
		}
		if baseRS.Length() < MinLength {
			continue
		}
		midpoint := baseRS.PosAtFactor(baseRS.Length()/2).Point()
		i, j := int(midpoint.X), int(midpoint.Y)
		if i < Padding || i >= dims[0]-Padding || j < Padding || j >= dims[1]-Padding {
			continue
		}
		if origPix[i][j] == 255 {
			continue
		}

		markSeen(baseRS)

		curRS := []common.RoadSegment{baseRS}
		q := []*common.Node{baseRS.Src(), baseRS.Dst()}
		for len(q) > 0 {
			node := q[len(q)-1]
			q = q[0:len(q)-1]
			for _, rs := range nodeToRS[node.ID] {
				if isSeen(rs) {
					continue
				}
				markSeen(rs)
				midpoint := rs.PosAtFactor(rs.Length()/2).Point()
				i, j := int(midpoint.X), int(midpoint.Y)
				if i < SmallDilation || i >= dims[0]-SmallDilation || j < SmallDilation || j >= dims[1]-SmallDilation {
					continue
				}
				if smallPix[i][j] == 255 {
					continue
				}
				curRS = append(curRS, rs)
				q = append(q, rs.Dst())
			}
		}

		var edges []*common.Edge
		var totalLength float64
		for _, rs := range curRS {
			edges = append(edges, rs.Edges...)
			totalLength += rs.Length()
		}
		if totalLength < MinTotalLength {
			continue
		}
		groups = append(groups, edges)
	}
	return groups
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

	// now find changed roads between consecutive timestamps at each tile
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
		var changedRoads []lib.ChangedRoad

		for i := 1; i < len(items); i++ {
			prevItem := items[i-1]
			nextItem := items[i]
			log.Printf("processing at tile %s[%d, %d]: timestamps %s and %s", tileKey.Region, tileKey.Tile[0], tileKey.Tile[1], prevItem.Timestamp, nextItem.Timestamp)
			addedRoads := findChange(prevItem.WithAll, nextItem.WithoutAll, dims)
			removedRoads := findChange(nextItem.WithAll, prevItem.WithoutAll, dims)
			log.Printf("... found %d added, %d removed", len(addedRoads), len(removedRoads))

			for _, group := range addedRoads {
				cr := ChangedRoadFromEdges(group)
				cr.Region = tileKey.Region
				cr.Tile = tileKey.Tile
				cr.OrigTimestamp = prevItem.Timestamp
				cr.NewTimestamp = nextItem.Timestamp
				cr.Deleted = false
				changedRoads = append(changedRoads, cr)
			}

			for _, group := range removedRoads {
				cr := ChangedRoadFromEdges(group)
				cr.Region = tileKey.Region
				cr.Tile = tileKey.Tile
				cr.OrigTimestamp = nextItem.Timestamp
				cr.NewTimestamp = prevItem.Timestamp
				cr.Deleted = true
				changedRoads = append(changedRoads, cr)
			}
		}

		bytes, err = json.Marshal(changedRoads)
		if err != nil {
			panic(err)
		}
		if err := ioutil.WriteFile(outFname, bytes, 0644); err != nil {
			panic(err)
		}
	}
}
