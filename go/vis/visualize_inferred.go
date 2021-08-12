package main

import (
	"../lib"
	"github.com/mitroadmaps/gomapinfer/common"
	"github.com/mitroadmaps/gomapinfer/image"

	"encoding/json"
	"fmt"
	"io/ioutil"
	"os"
	"path/filepath"
	"strconv"
)

const Padding = 128

func visualize(annotation lib.Annotation, jpgFname string, inferredFname string, baseFname string, gtFname string, allFname string, mode string) [][][3]uint8 {
	im := image.ReadImage(jpgFname)
	inferred, err := common.ReadGraph(inferredFname)
	if err != nil {
		panic(err)
	}
	basemap, err := common.ReadGraph(baseFname)
	if err != nil {
		panic(err)
	}
	gtmap, err := common.ReadGraph(gtFname)
	if err != nil {
		panic(err)
	}
	extramap, err := common.ReadGraph(allFname)
	if err != nil {
		panic(err)
	}

	clipPad := func(rect [4]int, padding int, dims [2]int) [4]int {
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

	window := clipPad(annotation.Cluster.Window, Padding, [2]int{len(im), len(im[0])})
	offset := [2]int{window[0], window[1]}
	im = image.Crop(im, window[0], window[1], window[2], window[3])
	rect := common.Rectangle{
		common.Point{float64(window[0]), float64(window[1])},
		common.Point{float64(window[2]), float64(window[3])},
	}

	drawSegment := func(segment common.Segment, color [3]uint8, width int) {
		sx := int(segment.Start.X) - offset[0]
		sy := int(segment.Start.Y) - offset[1]
		ex := int(segment.End.X) - offset[0]
		ey := int(segment.End.Y) - offset[1]
		for _, p := range common.DrawLineOnCells(sx, sy, ex, ey, len(im), len(im[0])) {
			for i := -width; i <= width; i++ {
				for j := -width; j <= width; j++ {
					x := p[0]+i
					y := p[1]+j
					if x < 0 || x >= len(im) || y < 0 || y >= len(im[x]) {
						continue
					}
					im[x][y] = color
				}
			}
		}
	}

	baseidx := basemap.GridIndex(128)
	gtidx := gtmap.GridIndex(128)
	extraidx := extramap.GridIndex(128)

	// highlight the changes with wide lines
	for _, change := range annotation.Cluster.Changes {
		var color [3]uint8
		if change.Deleted {
			color = [3]uint8{255, 0, 0}
		} else {
			color = [3]uint8{0, 255, 0}
		}
		for _, segment := range change.Segments {
			drawSegment(segment, color, 2)
		}
	}

	// draw the new graph in yellow
	if mode == "default" {
		for _, edge := range extraidx.Search(rect) {
			segment := edge.Segment()
			segment = common.Segment{
				segment.Start.Add(common.Point{3, 3}),
				segment.End.Add(common.Point{3, 3}),
			}
			drawSegment(segment, [3]uint8{255, 128, 0}, 0)
		}
		for _, edge := range gtidx.Search(rect) {
			segment := edge.Segment()
			segment = common.Segment{
				segment.Start.Add(common.Point{3, 3}),
				segment.End.Add(common.Point{3, 3}),
			}
			drawSegment(segment, [3]uint8{255, 255, 0}, 0)
		}
	}

	// draw the inferred graph in white
	if mode == "default" || mode == "inferred" {
		for _, edge := range inferred.Edges {
			segment := edge.Segment()
			segment = common.Segment{
				segment.Start.Add(common.Point{-3, -3}),
				segment.End.Add(common.Point{-3, -3}),
			}
			drawSegment(segment, [3]uint8{255, 255, 255}, 1)
		}
	}

	// draw the old graph in blue
	if mode == "default" {
		for _, edge := range baseidx.Search(rect) {
			segment := edge.Segment()
			drawSegment(segment, [3]uint8{0, 0, 255}, 0)
		}
	}

	return im
}

const BaseSuffix = "_2013-07-01.graph"
const GTSuffix = "_2020-07-01.graph"
const AllSuffix = "_2020-07-01_all.graph"

func main() {
	annotationFname := os.Args[1]
	annotationIdx, _ := strconv.Atoi(os.Args[2])
	jpgDir := os.Args[3]
	graphDir := os.Args[4]
	inferredDir := os.Args[5]
	mode := os.Args[6]
	outDir := os.Args[7]

	bytes, err := ioutil.ReadFile(annotationFname)
	if err != nil {
		panic(err)
	}
	var annotations []lib.Annotation
	if err := json.Unmarshal(bytes, &annotations); err != nil {
		panic(err)
	}

	annotation := annotations[annotationIdx]
	label := annotation.Cluster.Label()

	var jpgFname string
	for _, year := range []int{2020, 2019, 2018, 2017} {
		tryFname := filepath.Join(jpgDir, fmt.Sprintf("%s_%d.jpg", label, year))
		if _, err := os.Stat(tryFname); os.IsNotExist(err) {
			continue
		}
		jpgFname = tryFname
		break
	}

	baseFname := filepath.Join(graphDir, label+BaseSuffix)
	gtFname := filepath.Join(graphDir, label+GTSuffix)
	allFname := filepath.Join(graphDir, label+AllSuffix)
	inferredFname := filepath.Join(inferredDir, fmt.Sprintf("%d.graph", annotationIdx))
	im := visualize(annotation, jpgFname, inferredFname, baseFname, gtFname, allFname, mode)
	outFname := filepath.Join(outDir, fmt.Sprintf("%d.jpg", annotationIdx))
	image.WriteImage(outFname, im)
}
