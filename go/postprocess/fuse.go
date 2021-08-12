package main

// Fuse an inferred road network with a base map.
// We assume the inferred road network is only finding new roads, not removing existing ones.
// For each vertex that is suitably far from the base map, we conduct a DFS.
// Whenever we hit the base map during the search, we create a connection to the base map instead of
// continuing the search.

// Note: base maps are now per-annotation and should already be cropped to small window.
// The base maps can be generated with identity method.
// Or "base map" can be output of classify/apply_delroad method.

// We now offer two modes:
// - normal: output is merged base graph + inferred graph
// - onlynew: output is only the inferred components from inferred graph

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

const StartThreshold = 20
const CloseThreshold = 10

// minimum total length of edges in a connected component
// if less than this threshold, we don't fuse it into the graph
const LengthThreshold = 70

func fuse(inferred *common.Graph, base *common.Graph, mode string) *common.Graph {
	closestEdge := func(p common.Point, g *common.Graph, threshold float64) *common.Edge {
		var bestEdge *common.Edge
		var bestDistance float64
		for _, edge := range g.Edges {
			distance := edge.Segment().Distance(p)
			if distance >= threshold {
				continue
			}
			if bestEdge == nil || distance < bestDistance {
				bestEdge = edge
				bestDistance = distance
			}
		}
		return bestEdge
	}

	var ngraph *common.Graph
	if mode == "normal" {
		ngraph = base.Clone()
	} else if mode == "onlynew" {
		ngraph = &common.Graph{}
	}

	// we will add components to ngraph, but also maintain set of bad edges
	// for filtering ngraph later because we may find that some components end
	// up being smaller than the minimum size threshold
	badEdges := make(map[int]bool)

	nodemap := make(map[int]*common.Node)
	for _, node := range inferred.Nodes {
		if nodemap[node.ID] != nil {
			continue
		}
		if closestEdge(node.Point, base, StartThreshold) != nil {
			continue
		}
		nodemap[node.ID] = ngraph.AddNode(node.Point)
		q := []*common.Node{node}
		var curEdges []*common.Edge
		addBidirectionalEdge := func(n1 *common.Node, n2 *common.Node) {
			edges := ngraph.AddBidirectionalEdge(n1, n2)
			curEdges = append(curEdges, edges[0], edges[1])
		}
		isConnected := false // whether this component is connected to existing map
		for len(q) > 0 {
			cur := q[len(q)-1]
			q = q[0:len(q)-1]
			for _, edge := range cur.Out {
				dst := edge.Dst
				if nodemap[dst.ID] != nil {
					addBidirectionalEdge(nodemap[cur.ID], nodemap[dst.ID])
					continue
				}
				baseEdge := closestEdge(dst.Point, base, CloseThreshold)
				if baseEdge == nil {
					nodemap[dst.ID] = ngraph.AddNode(dst.Point)
					addBidirectionalEdge(nodemap[cur.ID], nodemap[dst.ID])
					q = append(q, dst)
					continue
				}
				if mode == "normal" {
					// dst is close to the base graph, so we need to connect it up
					// (1) find the corresponding edge in ngraph
					// (2) split that edge (if needed) and add a connection
					basePoint := baseEdge.ClosestPos(dst.Point).Point()
					nEdge := closestEdge(basePoint, ngraph, 9999)
					splitPos := nEdge.ClosestPos(dst.Point)
					var connectNode *common.Node
					if splitPos.Position <= 5 {
						connectNode = nEdge.Src
					} else if splitPos.Position >= nEdge.Segment().Length() - 5 {
						connectNode = nEdge.Dst
					} else {
						remainder := ngraph.SplitEdge(nEdge, splitPos.Position)
						connectNode = remainder.Src
					}
					nodemap[dst.ID] = connectNode
					addBidirectionalEdge(nodemap[cur.ID], nodemap[dst.ID])
					isConnected = true
				} else if mode == "onlynew" {
					// in onlynew mode, we stop the search here, but we keep dst where it is
					nodemap[dst.ID] = ngraph.AddNode(dst.Point)
					addBidirectionalEdge(nodemap[cur.ID], nodemap[dst.ID])
					isConnected = true
				}
			}
		}

		var totalLength float64
		for _, edge := range curEdges {
			totalLength += edge.Segment().Length()
		}
		// total length is doubled due to bidirectional edges
		// remove components that are too small, or are disconnected from the existing map
		if totalLength/2 < LengthThreshold || !isConnected {
			for _, edge := range curEdges {
				badEdges[edge.ID] = true
			}
		}
	}

	ngraph = ngraph.FilterEdges(badEdges)

	return ngraph
}

func main() {
	annotationFname := os.Args[1]
	mode := os.Args[2]
	baseDir := os.Args[3]
	inDir := os.Args[4]
	outDir := os.Args[5]

	bytes, err := ioutil.ReadFile(annotationFname)
	if err != nil {
		panic(err)
	}
	var annotations []lib.Annotation
	if err := json.Unmarshal(bytes, &annotations); err != nil {
		panic(err)
	}

	for annotationIdx, annotation := range annotations {
		graphFname := fmt.Sprintf("%d.graph", annotationIdx)
		inFname := filepath.Join(inDir, graphFname)
		if _, err := os.Stat(inFname); os.IsNotExist(err) {
			continue
		}
		log.Printf("%d/%d", annotationIdx, len(annotations))
		window := annotation.Cluster.Window
		rect := common.Rectangle{
			common.Point{float64(window[0]), float64(window[1])},
			common.Point{float64(window[2]), float64(window[3])},
		}.AddTol(192)
		baseGraph := lib.ReadGraph(filepath.Join(baseDir, graphFname))
		baseGraph = common.GraphFromEdges(baseGraph.GridIndex(128).Search(rect))
		inferred := lib.ReadGraph(inFname)
		inferred = common.GraphFromEdges(inferred.GridIndex(128).Search(rect))
		out := fuse(inferred, baseGraph, mode)
		if err := out.Write(filepath.Join(outDir, graphFname)); err != nil {
			panic(err)
		}
	}
}
