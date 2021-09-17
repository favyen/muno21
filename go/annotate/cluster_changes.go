package main

import (
	"github.com/favyen/muno21/go/lib"

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

const Padding = 16

func TimestampToIndex(timestamp string) int {
	year, _ := strconv.Atoi(strings.Split(timestamp, "-")[0])
	return year
}

func TimestampFromIndex(index int) string {
	return fmt.Sprintf("%d-07-01", index)
}

func GetEndTimeIndex(change lib.ChangedRoad) int {
	var timestamp string
	if change.Deleted {
		timestamp = change.OrigTimestamp
	} else {
		timestamp = change.NewTimestamp
	}
	return TimestampToIndex(timestamp)
}

func cluster(changes []lib.ChangedRoad) []lib.Cluster {
	seenIDs := make(map[int]bool)
	var clusters []lib.Cluster
	for id, change := range changes {
		if seenIDs[id] {
			continue
		}
		seenIDs[id] = true
		curChanges := []lib.ChangedRoad{change}

		rect := change.GetRectangle().AddTol(Padding)
		endTime := GetEndTimeIndex(change)
		timeWindow := [2]int{endTime-1, endTime+1}

		// repeatedly add changes to this cluster until an iteration that doesn't expand the cluster
		for {
			updated := false
			for otherID, otherChange := range changes {
				if seenIDs[otherID] {
					continue
				}
				otherRect := otherChange.GetRectangle().AddTol(Padding)
				otherTime := GetEndTimeIndex(otherChange)
				if !rect.Intersects(otherRect) {
					continue
				}
				if otherTime < timeWindow[0] || otherTime > timeWindow[1] {
					continue
				}
				// okay let's add to cluster then
				updated = true
				seenIDs[otherID] = true
				curChanges = append(curChanges, otherChange)

				rect = rect.Extend(otherRect.Min).Extend(otherRect.Max)
				if otherTime == timeWindow[0] {
					timeWindow[0] = otherTime-1
				}
				if otherTime == timeWindow[1] {
					timeWindow[1] = otherTime+1
				}
			}
			if !updated {
				break
			}
		}

		var size float64 = 0
		for _, change := range curChanges {
			for _, segment := range change.Segments {
				size += segment.Length()
			}
		}

		clusters = append(clusters, lib.Cluster{
			Region: change.Region,
			Tile: change.Tile,
			Changes: curChanges,
			FirstTimestamp: TimestampFromIndex(timeWindow[0]+1),
			LastTimestamp: TimestampFromIndex(timeWindow[1]-1),
			Window: [4]int{
				int(rect.Min.X),
				int(rect.Min.Y),
				int(rect.Max.X),
				int(rect.Max.Y),
			},
			Size: size,
		})
	}
	return clusters
}

func main() {
	changesDir := os.Args[1]
	outDir := os.Args[2]

	files, err := ioutil.ReadDir(changesDir)
	if err != nil {
		panic(err)
	}
	for _, fi := range files {
		if !strings.HasSuffix(fi.Name(), ".json") {
			continue
		}

		label := strings.Split(fi.Name(), ".json")[0]
		outFname := filepath.Join(outDir, label+".json")
		if _, err := os.Stat(outFname); err == nil {
			continue
		}

		log.Printf("processing %s", label)
		bytes, err := ioutil.ReadFile(filepath.Join(changesDir, fi.Name()))
		if err != nil {
			panic(err)
		}
		var changedRoads []lib.ChangedRoad
		if err := json.Unmarshal(bytes, &changedRoads); err != nil {
			panic(err)
		}

		clusters := cluster(changedRoads)
		sort.Slice(clusters, func(i, j int) bool {
			return clusters[i].Size > clusters[j].Size
		})
		log.Printf("%d changes -> %d clusters", len(changedRoads), len(clusters))

		bytes, err = json.Marshal(clusters)
		if err != nil {
			panic(err)
		}
		if err := ioutil.WriteFile(outFname, bytes, 0644); err != nil {
			panic(err)
		}
	}
}
