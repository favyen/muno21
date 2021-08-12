package main

import (
	"github.com/mitroadmaps/gomapinfer/common"
	"../lib"

	"fmt"
	"os"
	"path/filepath"
)

// Place markers every 2 m along each road in both graphs.
// Then score is based on one-to-one matching between inferred markers and ground truth markers.
// Matching distance is 8 m.

func getMarkers(rect common.Rectangle, g *common.Graph) []common.Point {
	var points []common.Point
	roadSegments := g.GetRoadSegments()
	seenEdges := make(map[int]bool)
	for _, rs := range roadSegments {
		if seenEdges[rs.Edges[0].ID] {
			continue
		}
		seenEdges[rs.Edges[0].ID] = true
		seenEdges[rs.Edges[len(rs.Edges)-1].ID] = true
		seenEdges[rs.Edges[0].GetOpposite().ID] = true
		seenEdges[rs.Edges[len(rs.Edges)-1].GetOpposite().ID] = true

		var pos float64 = 0
		for pos < rs.Length() {
			point := rs.PosAtFactor(pos).Point()
			if rect.Contains(point) {
				points = append(points, point)
			}
			pos += 2
		}
	}
	return points
}

func evaluate(rect common.Rectangle, g1 *common.Graph, g2 *common.Graph) (precision float64, recall float64) {
	points1 := getMarkers(rect, g1)
	points2 := getMarkers(rect, g2)
	idx2 := common.NewGridIndex(8)
	for i, p := range points2 {
		idx2.Insert(i, p.Bounds())
	}
	// one-to-one matching
	used2 := make(map[int]bool)
	var tp, fn int
	for _, p1 := range points1 {
		var best int = -1
		var bestDistance float64
		for _, i2 := range idx2.Search(p1.Bounds().AddTol(8)) {
			if used2[i2] {
				continue
			}
			p2 := points2[i2]
			d := p1.Distance(p2)
			if d > 8 {
				continue
			}
			if best == -1 || d < bestDistance {
				best = i2
				bestDistance = d
			}
		}
		if best == -1 {
			fn++
		} else {
			tp++
			used2[best] = true
		}
	}
	fp := len(points2) - len(used2)

	if tp == 0 {
		return 0, 0
	}
	precision = float64(tp) / float64(tp+fp)
	recall = float64(tp) / float64(tp+fn)
	return precision, recall
}

func evaluateWithExtra(rect common.Rectangle, gt *common.Graph, proposed *common.Graph, extra *common.Graph) float64 {
	precision, _ := evaluate(rect, extra, proposed)
	_, recall := evaluate(rect, gt, proposed)
	if precision == 0 || recall == 0 {
		return 0
	}
	return 2*precision*recall/(precision+recall)
}

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

	graphs := make(map[string]common.GraphGridIndex)
	getGraph := func(region string, tile [2]int, suffix string) common.GraphGridIndex {
		fname := fmt.Sprintf("%s_%d_%d", region, tile[0], tile[1]) + suffix
		if _, ok := graphs[fname]; !ok {
			fmt.Println("load graph", fname)
			graph := lib.ReadGraph(filepath.Join(graphDir, fname))
			graphs[fname] = graph.GridIndex(128)
		}
		return graphs[fname]
	}

	var scores [][]interface{}
	for annotationIdx, annotation := range annotations {
		if annotation.HasTag("nochange") {
			continue
		}
		cluster := annotation.Cluster
		if !testSet[cluster.Region] {
			continue
		}
		fmt.Println(annotationIdx, "/", len(annotations))
		rect := cluster.Rectangle().AddTol(128)
		inferred := lib.ReadGraph(filepath.Join(inferredDir, fmt.Sprintf("%d.graph", annotationIdx)))
		gtIndex := getGraph(cluster.Region, cluster.Tile, "_2020-07-01.graph")
		baseIndex := getGraph(cluster.Region, cluster.Tile, "_2013-07-01.graph")
		extraIndex := getGraph(cluster.Region, cluster.Tile, "_2020-07-01_extra.graph")
		gtGraph := common.GraphFromEdges(gtIndex.Search(rect))
		baseGraph := common.GraphFromEdges(baseIndex.Search(rect))
		extraGraph := common.GraphFromEdges(extraIndex.Search(rect))
		score1 := evaluateWithExtra(rect, gtGraph, baseGraph, extraGraph)
		score2 := evaluateWithExtra(rect, gtGraph, inferred, extraGraph)
		improvement := (score2 - score1) / (1 - score1)
		scores = append(scores, []interface{}{annotationIdx, improvement})
	}

	outFname := filepath.Join(inferredDir, "geo.json")
	lib.WriteJSONFile(outFname, scores)
}
