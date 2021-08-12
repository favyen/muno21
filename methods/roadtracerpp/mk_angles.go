package main

import (
	"github.com/mitroadmaps/gomapinfer/common"

	"bytes"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"math"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

const RoadWidth = 18
const D = 12
const TrainGraphSuffix = "_2020-07-01.graph"

type GraphContainer struct {
	Graph *common.Graph
	Index common.GraphGridIndex
	RoadSegments []common.RoadSegment
	EdgeToSegment map[int]common.RoadSegment
}

func main() {
	graphDir := os.Args[1]
	sizesFname := os.Args[2]
	anglesDir := os.Args[3]

	nthreads := 1
	if len(os.Args) >= 5 {
		var err error
		nthreads, err = strconv.Atoi(os.Args[4])
		if err != nil {
			panic(err)
		}
	}

	files, err := ioutil.ReadDir(graphDir)
	if err != nil {
		panic(err)
	}

	gcs := make(map[string]GraphContainer)
	for _, fi := range files {
		if !strings.HasSuffix(fi.Name(), TrainGraphSuffix) {
			continue
		}
		label := strings.Split(fi.Name(), TrainGraphSuffix)[0]
		log.Printf("reading graph for %s", label)
		graph, err := common.ReadGraph(filepath.Join(graphDir, fi.Name()))
		if err != nil {
			panic(err)
		}
		roadSegments := graph.GetRoadSegments()
		edgeToSegment := make(map[int]common.RoadSegment)
		for _, rs := range roadSegments {
			for _, edge := range rs.Edges {
				edgeToSegment[edge.ID] = rs
			}
		}
		gcs[label] = GraphContainer{
			graph,
			graph.GridIndex(256),
			roadSegments,
			edgeToSegment,
		}
	}

	var sizes map[string][2]int
	data, err := ioutil.ReadFile(sizesFname)
	if err != nil {
		panic(err)
	}
	if err := json.Unmarshal(data, &sizes); err != nil {
		panic(err)
	}

	processTask := func(label string) {
		gc := gcs[label]
		dims := sizes[label]
		values := make([][][64]uint8, dims[0]/4)
		for i := range values {
			values[i] = make([][64]uint8, dims[1]/4)
		}
		for i := 0; i < dims[0]/4; i++ {
			for j := 0; j < dims[1]/4; j++ {
				p := common.Point{float64(i*4), float64(j*4)}

				// match to nearest edgepos
				var closestEdge *common.Edge
				var closestDistance float64
				for _, edge := range gc.Index.Search(p.Bounds().AddTol(RoadWidth)) {
					distance := edge.Segment().Distance(p)
					if distance < RoadWidth && (closestEdge == nil || distance < closestDistance) {
						closestEdge = edge
						closestDistance = distance
					}
				}
				if closestEdge == nil {
					continue
				}
				pos := closestEdge.ClosestPos(p)

				// get potential RS
				curEdge := pos.Edge
				curRS := gc.EdgeToSegment[curEdge.ID]
				oppositeRS := gc.EdgeToSegment[curEdge.GetOpposite().ID]
				potentialRS := []common.RoadSegment{curRS, oppositeRS}

				// get angles
				var buckets []int
				for _, rs := range potentialRS {
					pos := rs.ClosestPos(p)
					targetPositions := gc.Graph.Follow(common.FollowParams{
						SourcePos: pos,
						Distance: D,
					})

					for _, targetPos := range targetPositions {
						targetPoint := targetPos.Point()
						targetVector := targetPoint.Sub(p)
						edgeVector := targetPos.Edge.Segment().Vector()
						avgVector := targetVector.Scale(1 / targetVector.Magnitude()).Add(edgeVector.Scale(1 / edgeVector.Magnitude()))
						angle := common.Point{1, 0}.SignedAngle(avgVector)
						bucket := int((angle + math.Pi) * 64 / math.Pi / 2)
						if bucket < 0 || bucket > 63 {
							fmt.Printf("bad bucket: %v\n", bucket)
							fmt.Printf("target vector: %v\n", targetVector)
							fmt.Printf("edge vector: %v\n", edgeVector)
							fmt.Printf("avg vector: %v\n", avgVector)
							fmt.Printf("angle: %v\n", angle)
							fmt.Printf("rs length: %v\n", rs.Length())
						}
						buckets = append(buckets, bucket)
					}
				}

				// set targets
				for _, bucket := range buckets {
					for offset := 0; offset < 9; offset++ {
						weight := uint8(math.Pow(0.75, float64(offset)) * 255)
						b1 := (bucket + offset) % 64
						b2 := (bucket - offset + 64) % 64
						if weight > values[i][j][b1] {
							values[i][j][b1] = weight
						}
						if weight > values[i][j][b2] {
							values[i][j][b2] = weight
						}
					}
				}
			}
		}

		var buf bytes.Buffer
		for i := range values {
			for j := range values[i] {
				buf.Write([]byte(values[i][j][:]))
			}
		}
		outFname := filepath.Join(anglesDir, label+".bin")
		if err := ioutil.WriteFile(outFname, buf.Bytes(), 0644); err != nil {
			panic(err)
		}
	}

	var labels []string
	for label := range gcs {
		labels = append(labels, label)
	}

	fmt.Println("launching workers")
	taskCh := make(chan string)
	doneCh := make(chan bool)
	for i := 0; i < nthreads; i++ {
		go func() {
			for task := range taskCh {
				processTask(task)
			}
			doneCh <- true
		}()
	}
	fmt.Println("running tasks")
	for i, label := range labels {
		if i % 10 == 0 {
			fmt.Printf("... task progress: %d/%d\n", i, len(labels))
		}
		taskCh <- label
	}
	close(taskCh)
	for i := 0; i < nthreads; i++ {
		<- doneCh
	}
}
