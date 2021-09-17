package main

import (
	"github.com/favyen/muno21/go/lib"
	"github.com/mitroadmaps/gomapinfer/common"

	"encoding/json"
	"fmt"
	"io/ioutil"
	"os"
	"path/filepath"
	"strings"
	"sync"
)

func main() {
	inDir := os.Args[1]
	outDir := os.Args[2]

	regionsByName := make(map[string]lib.Region)
	for _, region := range lib.Regions {
		regionsByName[region.Name] = region
	}

	var sizes map[string][2]int
	bytes, err := ioutil.ReadFile("sizes.json")
	if err != nil {
		panic(err)
	}
	if err := json.Unmarshal(bytes, &sizes); err != nil {
		panic(err)
	}

	f := func(label string) {
		fmt.Println(label)

		parts := strings.Split(label, "_")
		name := parts[0]
		timestamp := parts[1]

		region := regionsByName[name]
		for i := 0; i < region.Width; i++ {
			for j := 0; j < region.Height; j++ {
				tileOffset := common.Point{region.Start.X + 0.1*float64(i), region.Start.Y + 0.1*float64(j)}
				bounds := common.Rectangle{
					tileOffset,
					tileOffset.Add(common.Point{0.1, 0.1}),
				}

				tileLabel := fmt.Sprintf("%s_%d_%d", name, i, j)
				inPath := filepath.Join(inDir, label+".pbf")
				outPath := filepath.Join(outDir, fmt.Sprintf("%s_%s.graph", tileLabel, timestamp))
				outAllPath := filepath.Join(outDir, fmt.Sprintf("%s_%s_all.graph", tileLabel, timestamp))
				outTrainPath := filepath.Join(outDir, fmt.Sprintf("%s_%s_train.graph", tileLabel, timestamp))

				imageDims, ok := sizes[tileLabel]
				if !ok {
					continue
				}

				geoToPixel := func(graph *common.Graph) {
					for _, node := range graph.Nodes {
						// point normalized to 0-1 wrt the current tile
						normalized := common.Point{
							(node.Point.X - bounds.Min.X) / (bounds.Max.X - bounds.Min.X),
							(bounds.Max.Y - node.Point.Y) / (bounds.Max.Y - bounds.Min.Y),
						}
						npoint := common.Point{
							normalized.X * float64(imageDims[0]),
							normalized.Y * float64(imageDims[1]),
						}
						node.Point = npoint
					}
				}

				boundList := []common.Rectangle{bounds.AddTol(0.01)}

				// no parking
				if _, err := os.Stat(outPath); os.IsNotExist(err) {
					graphs, err := common.LoadOSMMultiple(inPath, boundList, common.OSMOptions{
						Verbose: true,
						NoParking: true,
						CustomBlacklist: []string{
							"pedestrian",
							"footway",
							"bridleway",
							"steps",
							"path",
							"sidewalk",
							"cycleway",
							"proposed",
							"construction",
							"bus_stop",
							"crossing",
							"elevator",
							"emergency_access_point",
							"escape",
							"give_way",
							"track",
							"service",
						},
					})
					if err != nil {
						panic(err)
					}
					geoToPixel(graphs[0])
					if err := graphs[0].Write(outPath); err != nil {
						panic(err)
					}
				}

				// with everything
				if _, err := os.Stat(outAllPath); os.IsNotExist(err) {
					graphs, err := common.LoadOSMMultiple(inPath, boundList, common.OSMOptions{
						Verbose: true,
						CustomBlacklist: []string{
							"crossing",
							"give_way",
						},
					})
					if err != nil {
						panic(err)
					}
					geoToPixel(graphs[0])
					if err := graphs[0].Write(outAllPath); err != nil {
						panic(err)
					}
				}

				// for training: do include parking and service roads but no footpaths and such
				if _, err := os.Stat(outTrainPath); os.IsNotExist(err) && timestamp == "2020-07-01" {
					graphs, err := common.LoadOSMMultiple(inPath, boundList, common.OSMOptions{
						Verbose: true,
						CustomBlacklist: []string{
							"pedestrian",
							"footway",
							"bridleway",
							"steps",
							"path",
							"sidewalk",
							"cycleway",
							"proposed",
							"construction",
							"bus_stop",
							"crossing",
							"elevator",
							"emergency_access_point",
							"escape",
							"give_way",
							"track",
						},
					})
					if err != nil {
						panic(err)
					}
					geoToPixel(graphs[0])
					if err := graphs[0].Write(outTrainPath); err != nil {
						panic(err)
					}
				}
			}
		}
	}

	ch := make(chan string)
	var wg sync.WaitGroup
	for i := 0; i < 24; i++ {
		wg.Add(1)
		go func() {
			for label := range ch {
				f(label)
			}
			wg.Done()
		}()
	}

	files, err := ioutil.ReadDir(inDir)
	if err != nil {
		panic(err)
	}
	for _, fi := range files {
		if !strings.HasSuffix(fi.Name(), ".pbf") {
			continue
		}
		label := strings.Split(fi.Name(), ".pbf")[0]
		ch <- label
	}
	close(ch)
	wg.Wait()
}
