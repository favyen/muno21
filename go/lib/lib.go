package lib

import (
	"github.com/mitroadmaps/gomapinfer/common"
	"encoding/json"
	"fmt"
	"io/ioutil"
)

type ChangedRoad struct {
	// Position in new image
	EdgeIDs []int
	Segments []common.Segment

	// which image it's in
	Region string
	Tile [2]int

	// the timestamps
	OrigTimestamp string
	NewTimestamp string

	// is new timestamp before orig timestamp?
	// i.e., was this a road that got deleted
	Deleted bool
}

func (change ChangedRoad) GetRectangle() common.Rectangle {
	rect := common.EmptyRectangle
	for _, segment := range change.Segments {
		rect = rect.Extend(segment.Start).Extend(segment.End)
	}
	return rect
}

type Cluster struct {
	Region string
	Tile [2]int

	Changes []ChangedRoad
	FirstTimestamp string
	LastTimestamp string
	Window [4]int
	Size float64
}

func (cluster Cluster) Label() string {
	return fmt.Sprintf("%s_%d_%d", cluster.Region, cluster.Tile[0], cluster.Tile[1])
}

func (cluster Cluster) Rectangle() common.Rectangle {
	w := cluster.Window
	return common.Rectangle{
		common.Point{float64(w[0]), float64(w[1])},
		common.Point{float64(w[2]), float64(w[3])},
	}
}

type Annotation struct {
	Cluster Cluster
	Idx int
	// when did construction/bulldozing start/end?
	Years [2]int
	// e.g. primary, secondary, tertiary, residential
	RoadType string
	// subset of {constructed, bulldozed, was_missing, was_incorrect}
	Tags []string
}

func (annot Annotation) HasTag(tag string) bool {
	for _, t := range annot.Tags {
		if tag == t {
			return true
		}
	}
	return false
}

func ReadJSONFile(fname string, x interface{}) {
	bytes, err := ioutil.ReadFile(fname)
	if err != nil {
		panic(err)
	}
	if err := json.Unmarshal(bytes, x); err != nil {
		panic(err)
	}
}

func WriteJSONFile(fname string, x interface{}) {
	bytes, err := json.Marshal(x)
	if err != nil {
		panic(err)
	}
	if err := ioutil.WriteFile(fname, bytes, 0644); err != nil {
		panic(err)
	}
}

func ReadGraph(fname string) *common.Graph {
	g, err := common.ReadGraph(fname)
	if err != nil {
		panic(err)
	}
	return g
}

// Pad a window, but clip it to some bounding dimensions.
func ClipPad(rect [4]int, padding int, dims [2]int) [4]int {
   rect = [4]int{
	   rect[0]-padding,
	   rect[1]-padding,
	   rect[2]+padding,
	   rect[3]+padding,
   }
   if rect[0] < 0 {
	   rect[0] = 0
   }
   if rect[1] < 0 {
	   rect[1] = 0
   }
   if rect[2] >= dims[0] {
	   rect[2] = dims[0]-1
   }
   if rect[3] >= dims[1] {
	   rect[3] = dims[1]-1
   }
   return rect
}
