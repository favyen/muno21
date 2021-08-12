package main

import (
	"../lib"

	"encoding/json"
	"io/ioutil"
	"log"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

func main() {
	clusterDir := os.Args[1]
	annotationFname := os.Args[2]
	nochangeDir := os.Args[3]
	outFname := os.Args[4]

	// read all clusters
	clustersByLabel := make(map[string][]lib.Cluster)
	files, err := ioutil.ReadDir(clusterDir)
	if err != nil {
		panic(err)
	}
	for _, fi := range files {
		label := strings.Split(fi.Name(), ".")[0]
		var clusters []lib.Cluster
		bytes, err := ioutil.ReadFile(filepath.Join(clusterDir, fi.Name()))
		if err != nil {
			panic(err)
		}
		if err := json.Unmarshal(bytes, &clusters); err != nil {
			panic(err)
		}
		clustersByLabel[label] = clusters
	}

	// parse annotations
	bytes, err := ioutil.ReadFile(annotationFname)
	if err != nil {
		panic(err)
	}
	var curLabel string
	var annotations []lib.Annotation
	for _, line := range strings.Split(string(bytes), "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		if line[0] == '!' {
			curLabel = line[1:]
			continue
		}
		if !strings.Contains(line, ":") {
			log.Printf("skipping weird line [%s]", line)
			continue
		}
		parts := strings.Split(line, ":")
		clusterIdx, err := strconv.Atoi(parts[0])
		if err != nil {
			panic(err)
		}
		cluster := clustersByLabel[curLabel][clusterIdx]
		parts = strings.Split(parts[1], ";")
		var years [2]int
		if parts[0] != "" {
			yearParts := strings.Split(parts[0], "-")
			years[0], err = strconv.Atoi(yearParts[0])
			if err != nil {
				panic(err)
			}
			if len(yearParts) >= 2 {
				years[1], err = strconv.Atoi(yearParts[1])
				if err != nil {
					panic(err)
				}
			} else {
				years[1] = years[0]
			}
		}
		var roadType string
		if len(parts) >= 2 {
			roadType = parts[1]
		}

		// determine the tags
		tagSet := make(map[string]bool)
		hasYear := years[0] != 0
		for _, change := range cluster.Changes {
			if change.Deleted && hasYear {
				tagSet["bulldozed"] = true
			}
			if change.Deleted && !hasYear {
				tagSet["was_incorrect"] = true
			}
			if !change.Deleted && hasYear {
				tagSet["constructed"] = true
			}
			if !change.Deleted && !hasYear {
				tagSet["was_missing"] = true
			}
		}
		var tags []string
		for tag := range tagSet {
			tags = append(tags, tag)
		}

		annotations = append(annotations, lib.Annotation{
			Cluster: cluster,
			Idx: clusterIdx,
			Years: years,
			RoadType: roadType,
			Tags: tags,
		})
	}

	// add in the nochange clusters
	files, err = ioutil.ReadDir(nochangeDir)
	if err != nil {
		panic(err)
	}
	for _, fi := range files {
		bytes, err := ioutil.ReadFile(filepath.Join(nochangeDir, fi.Name()))
		if err != nil {
			panic(err)
		}
		var clusters []lib.Cluster
		if err := json.Unmarshal(bytes, &clusters); err != nil {
			panic(err)
		}
		for _, cluster := range clusters {
			annotations = append(annotations, lib.Annotation{
				Cluster: cluster,
				Idx: -1,
				Tags: []string{"nochange"},
			})
		}
	}

	bytes, err = json.Marshal(annotations)
	if err != nil {
		panic(err)
	}
	if err := ioutil.WriteFile(outFname, bytes, 0644); err != nil {
		panic(err)
	}
}
