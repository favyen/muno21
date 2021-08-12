package main

// Remove inferred segments that correspond to parking/service/other paths in _all.graph.
// (only if they don't appear in the ground truth graph)

import (
	"../lib"
	"github.com/mitroadmaps/gomapinfer/common"

	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"os"
	"path/filepath"
)

// distance threshold
// we want to remove inferred segments that are within Threshold of _all.graph all along the segment,
// but not within Threshold of gt graph all along the segment.
const Threshold = 20

const GtSuffix string = "_2020-07-01.graph"
const AllSuffix string = "_2020-07-01_all.graph"

func prune(inferred *common.Graph, extraEdges common.GraphGridIndex, gtEdges common.GraphGridIndex) *common.Graph {
	isClose := func(p common.Point, edges common.GraphGridIndex) bool {
		for _, edge := range edges.Search(p.Bounds().AddTol(Threshold)) {
			if edge.Segment().Distance(p) < Threshold {
				return true
			}
		}
		return false
	}

	badEdges := make(map[int]bool)
	roadSegments := inferred.GetRoadSegments()
	for _, rs := range roadSegments {
		length := rs.Length()
		closeExtra := true
		closeGT := true
		for _, factor := range []float64{0, 0.25, 0.5, 0.75, 1.0} {
			p := rs.PosAtFactor(factor*length).Point()
			if !isClose(p, extraEdges) {
				closeExtra = false
				break
			}
			if !isClose(p, gtEdges) {
				closeGT = false
			}
		}
		if !closeExtra || closeGT {
			continue
		}

		// bad road segment (close to extra but not gt)
		for _, edge := range rs.Edges {
			badEdges[edge.ID] = true
		}
	}

	return inferred.FilterEdges(badEdges)
}

func main() {
	annotationFname := os.Args[1]
	graphDir := os.Args[2]
	inDir := os.Args[3]
	outDir := os.Args[4]

	bytes, err := ioutil.ReadFile(annotationFname)
	if err != nil {
		panic(err)
	}
	var annotations []lib.Annotation
	if err := json.Unmarshal(bytes, &annotations); err != nil {
		panic(err)
	}

	type GraphItem struct {
		WithAll common.GraphGridIndex
		WithoutAll common.GraphGridIndex
	}
	graphs := make(map[string]GraphItem)
	getGraphItem := func(label string) GraphItem {
		if _, ok := graphs[label]; !ok {
			log.Printf("load graph at %s", label)
			withAll, err := common.ReadGraph(filepath.Join(graphDir, label+AllSuffix))
			if err != nil {
				panic(err)
			}
			withoutAll, err := common.ReadGraph(filepath.Join(graphDir, label+GtSuffix))
			if err != nil {
				panic(err)
			}
			graphs[label] = GraphItem{
				WithAll: withAll.GridIndex(128),
				WithoutAll: withoutAll.GridIndex(128),
			}
		}
		return graphs[label]
	}

	for annotationIdx, annotation := range annotations {
		inFname := filepath.Join(inDir, fmt.Sprintf("%d.graph", annotationIdx))
		if _, err := os.Stat(inFname); os.IsNotExist(err) {
			continue
		}
		log.Printf("%d/%d", annotationIdx, len(annotations))
		graphItem := getGraphItem(annotation.Cluster.Label())
		inferred, err := common.ReadGraph(inFname)
		if err != nil {
			panic(err)
		}
		out := prune(inferred, graphItem.WithAll, graphItem.WithoutAll)
		if err := out.Write(filepath.Join(outDir, fmt.Sprintf("%d.graph", annotationIdx))); err != nil {
			panic(err)
		}
	}
}
