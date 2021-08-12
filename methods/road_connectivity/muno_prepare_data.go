package main

import (
	"github.com/mitroadmaps/gomapinfer/common"
	"github.com/mitroadmaps/gomapinfer/image"

	"encoding/json"
	"io/ioutil"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"strings"
	"sync"
)

func gaussian(x float64) uint8 {
	val := math.Exp(-x * x / 30)
	return uint8(val * 255)
}

func main() {
	graphDir := os.Args[1]
	sizesFname := os.Args[2]
	trainFname := os.Args[3]
	outDir := os.Args[4]

	var sizes map[string][2]int
	bytes, err := ioutil.ReadFile(sizesFname)
	if err != nil {
		panic(err)
	}
	if err := json.Unmarshal(bytes, &sizes); err != nil {
		panic(err)
	}
	var trainRegions []string
	bytes, err = ioutil.ReadFile(trainFname)
	if err != nil {
		panic(err)
	}
	if err := json.Unmarshal(bytes, &trainRegions); err != nil {
		panic(err)
	}
	trainSet := make(map[string]bool)
	for _, region := range trainRegions {
		trainSet[region] = true
	}

	amount := 8
	process := func(label string) {
		fmt.Println(label)
		dims := sizes[label]
		graph, err := common.ReadGraph(filepath.Join(graphDir, label+"_2020-07-01.graph"))
		if err != nil {
			panic(err)
		}
		values := make([][]uint8, dims[0])
		for i := range values {
			values[i] = make([]uint8, dims[1])
		}
		for _, edge := range graph.Edges {
			segment := edge.Segment()
			for _, pos := range common.DrawLineOnCells(int(segment.Start.X), int(segment.Start.Y), int(segment.End.X), int(segment.End.Y), dims[0], dims[1]) {
				for i := -amount; i <= amount; i++ {
					for j := -amount; j <= amount; j++ {
						x := pos[0] + i
						y := pos[1] + j
						if x < 0 || x >= dims[0] || y < 0 || y >= dims[1] {
							continue
						}
						d := math.Sqrt(float64(i*i+j*j))
						if d > float64(amount) {
							continue
						}
						val := gaussian(d)
						if val < values[x][y] {
							continue
						}
						values[x][y] = val
					}
				}
			}
		}

		image.WriteGrayImage(filepath.Join(outDir, label+".png"), values)
	}

	fmt.Println("launching workers")
	ch := make(chan string)
	var wg sync.WaitGroup
	for i := 0; i < 24; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for label := range ch {
				process(label)
			}
		}()
	}
	fmt.Println("running tasks")
	for label := range sizes {
		region := strings.Split(label, "_")[0]
		if !trainSet[region] {
			continue
		}
		ch <- label
	}
	close(ch)
	wg.Wait()
}
