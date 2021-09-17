package main

import (
	"github.com/favyen/muno21/go/lib"
	"github.com/mitroadmaps/gomapinfer/common"

	"fmt"
	"log"
	"os"
	"path/filepath"
)

// Merge the annotated extra edges (extra.json) into the _all graphs.

// Create new graph vertex unless existing edge is less than this threshold away from an extra segment.
const DistanceThreshold float64 = 15
// Snap to an existing vertex instead of splitting if distance to closest vertex is less than this threshold.
// Must be smaller than DistanceThreshold.
const SnapThreshold float64 = 15

func main() {
	annotationFname := os.Args[1]
	extraFname := os.Args[2]
	graphDir := os.Args[3]

	// Load annotations.
	var annotations []lib.Annotation
	lib.ReadJSONFile(annotationFname, &annotations)

	// Load labels.
	var labels [][][4]int
	if _, err := os.Stat(extraFname); err == nil {
		lib.ReadJSONFile(extraFname, &labels)
	}

	// Construct map from tile to list of edges we want to add.
	type TileKey struct {
		Region string
		Tile [2]int
	}
	newSegments := make(map[TileKey][]common.Segment)
	for annotIdx := range labels {
		cluster := annotations[annotIdx].Cluster
		tileKey := TileKey{cluster.Region, cluster.Tile}
		if newSegments[tileKey] == nil {
			newSegments[tileKey] = []common.Segment{}
		}
		for _, line := range labels[annotIdx] {
			segment := common.Segment{
				common.Point{float64(line[0]), float64(line[1])},
				common.Point{float64(line[2]), float64(line[3])},
			}
			newSegments[tileKey] = append(newSegments[tileKey], segment)
		}
	}

	// Incorporate segments into the graphs.
	for tileKey, segments := range newSegments {
		log.Println(tileKey)
		// Load existing road network.
		graph, err := common.ReadGraph(filepath.Join(graphDir, fmt.Sprintf("%s_%d_%d_2020-07-01_all.graph", tileKey.Region, tileKey.Tile[0], tileKey.Tile[1])))
		if err != nil {
			panic(err)
		}

		// Helper function to get a graph vertex for the given point.
		// The vertex may come from splitting an existing edge, or from creating a new one.
		getNode := func(p common.Point) *common.Node {
			var bestEdge *common.Edge = nil
			var bestDistance float64
			for _, edge := range graph.Edges {
				d := edge.Segment().Distance(p)
				if d > DistanceThreshold {
					continue
				}
				if bestEdge == nil || d < bestDistance {
					bestEdge = edge
					bestDistance = d
				}
			}

			if bestEdge == nil {
				return graph.AddNode(p)
			}

			if bestEdge.Src.Point.Distance(p) < SnapThreshold {
				return bestEdge.Src
			} else if bestEdge.Dst.Point.Distance(p) < SnapThreshold {
				return bestEdge.Dst
			}

			splitLength := bestEdge.Segment().Project(p, false)
			remainderEdge := graph.SplitEdge(bestEdge, splitLength)
			return remainderEdge.Src
		}

		for _, segment := range segments {
			src := getNode(segment.Start)
			dst := getNode(segment.End)
			graph.AddBidirectionalEdge(src, dst)
		}

		err = graph.Write(filepath.Join(graphDir, fmt.Sprintf("%s_%d_%d_2020-07-01_extra.graph", tileKey.Region, tileKey.Tile[0], tileKey.Tile[1])))
		if err != nil {
			panic(err)
		}
	}
}
