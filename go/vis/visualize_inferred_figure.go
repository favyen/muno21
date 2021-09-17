package main

import (
	"github.com/favyen/muno21/go/lib"
	"github.com/mitroadmaps/gomapinfer/common"
	"github.com/mitroadmaps/gomapinfer/image"

	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
	"sync"
)

/*

import os
import random # to avoid biased picking of output examples
html = '''
<html>
<body>
<table>
	<thead>
		<tr>
			<td>#</td>
			<td>2012</td>
			<td>2019</td>
			<td>Ground Truth</td>
			<td>RoadTracer+Fuse</td>
			<td>RecurrentUNet+Fuse</td>
			<td>Sat2Graph+Fuse</td>
			<td>RoadConnectivity+Fuse</td>
			<td>MAiD</td>
			<td>MAiD+Prune-Spurious</td>
			<td>Remove-Incorrect</td>
		</tr>
	</thead>
	<tbody>
'''
fnames = os.listdir('.')
random.shuffle(fnames)
for fname in fnames:
	if '_gt.png' not in fname:
		continue
	label = fname.split('_gt.png')[0]
	html += '''
		<tr>
			<td>{}</td>
			<td><img src="{}_old.png" style="max-width:500px" /></td>
			<td><img src="{}_new.png" style="max-width:500px" /></td>
			<td><img src="{}_gt.png" style="max-width:500px" /></td>
			<td><img src="{}_0.png" style="max-width:500px" /></td>
			<td><img src="{}_1.png" style="max-width:500px" /></td>
			<td><img src="{}_2.png" style="max-width:500px" /></td>
			<td><img src="{}_3.png" style="max-width:500px" /></td>
			<td><img src="{}_4.png" style="max-width:500px" /></td>
			<td><img src="{}_5.png" style="max-width:500px" /></td>
			<td><img src="{}_6.png" style="max-width:500px" /></td>
		</tr>
	'''.format(label, label, label, label, label, label, label, label, label, label, label)
html += '''
	</tbody>
</table>
</body>
</html>
'''
with open('index.html', 'w') as f:
	f.write(html)

*/

const Padding = 128

func DrawSegment(im [][][3]uint8, segment common.Segment, offset [2]int, color [3]uint8, width int) {
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

const Dilation int = 8

func visualize(annotation lib.Annotation, oldIm [][][3]uint8, newIm [][][3]uint8, oldGraph common.GraphGridIndex, newGraph common.GraphGridIndex, extraGraph common.GraphGridIndex, inferredGraphs []*common.Graph, outPrefix string) {
	window := lib.ClipPad(annotation.Cluster.Window, 128, [2]int{len(oldIm), len(newIm[0])})
	offset := [2]int{window[0], window[1]}
	rect := common.Rectangle{
		common.Point{float64(window[0]), float64(window[1])},
		common.Point{float64(window[2]), float64(window[3])},
	}
	dims := [2]int{window[2]-window[0], window[3]-window[1]}

	// aerial image
	crop := image.Crop(newIm, window[0], window[1], window[2], window[3])
	image.WriteImage(outPrefix+"new.png", crop)
	crop = image.Crop(oldIm, window[0], window[1], window[2], window[3])
	image.WriteImage(outPrefix+"old.png", crop)

	baseEdges := oldGraph.Search(rect)
	gtEdges := newGraph.Search(rect)
	extraEdges := extraGraph.Search(rect)

	// inferred pixels far from ground truth: render red
	// inferred pixels close to ground truth but also base map: render black
	// inferred pixels close to ground truth only: render green
	// base pixels that are close to ground truth but not inferred: render orange
	// base pixels that are in neither ground truth nor inferred: render blue
	render := func(edges []*common.Edge, extra bool, fname string) {
		// first need to get dilated inferred, ground truth, and base map
		baseDilate := image.MakeGrayImage(dims[0], dims[1], 0)
		gtDilate := image.MakeGrayImage(dims[0], dims[1], 0)
		inferredDilate := image.MakeGrayImage(dims[0], dims[1], 0)
		basePix := image.MakeGrayImage(dims[0], dims[1], 0)
		inferredPix := image.MakeGrayImage(dims[0], dims[1], 0)
		drawGrayGraph := func(im [][]uint8, edges []*common.Edge) {
			for _, edge := range edges {
				sx := int(edge.Src.Point.X) - offset[0]
				sy := int(edge.Src.Point.Y) - offset[1]
				ex := int(edge.Dst.Point.X) - offset[0]
				ey := int(edge.Dst.Point.Y) - offset[1]
				for _, p := range common.DrawLineOnCells(sx, sy, ex, ey, dims[0], dims[1]) {
					im[p[0]][p[1]] = 255
				}
			}
		}
		drawGrayGraph(baseDilate, baseEdges)
		drawGrayGraph(gtDilate, gtEdges)
		drawGrayGraph(inferredDilate, edges)
		drawGrayGraph(basePix, baseEdges)
		drawGrayGraph(inferredPix, edges)
		lib.Dilate(baseDilate, Dilation+2)
		lib.Dilate(gtDilate, Dilation)
		lib.Dilate(inferredDilate, Dilation+2)

		crop := image.MakeImage(dims[0], dims[1], [3]uint8{255, 255, 255})

		if extra {
			for _, edge := range extraEdges {
				segment := edge.Segment()
				DrawSegment(crop, segment, offset, [3]uint8{230, 230, 0}, 1)
			}
		}

		for i := 0; i < dims[0]; i++ {
			for j := 0; j < dims[1]; j++ {
				if inferredPix[i][j] == 255 {
					if gtDilate[i][j] == 0 {
						image.DrawRect(crop, i, j, 2, [3]uint8{230, 0, 0})
					} else if baseDilate[i][j] == 255 {
						image.DrawRect(crop, i, j, 2, [3]uint8{0, 0, 0})
					} else {
						image.DrawRect(crop, i, j, 2, [3]uint8{0, 230, 0})
					}
				}
				if basePix[i][j] == 255 && inferredDilate[i][j] == 0 {
					if gtDilate[i][j] == 255 {
						image.DrawRect(crop, i, j, 2, [3]uint8{255, 165, 0})
					} else {
						image.DrawRect(crop, i, j, 2, [3]uint8{0, 0, 255})
					}
				}
			}
		}
		image.WriteImage(fname, crop)
	}

	// base map and ground truth
	render(gtEdges, true, outPrefix+"gt.png")

	for graphIdx, inferredGraph := range inferredGraphs {
		render(inferredGraph.Edges, false, outPrefix+fmt.Sprintf("%d.png", graphIdx))
	}
}

func main() {
	annotationFname := os.Args[1]
	jpgDir := os.Args[2]
	graphDir := os.Args[3]
	inferredDirs := strings.Split(os.Args[4], ",")
	testFname := os.Args[5]
	outDir := os.Args[6]

	var annotations []lib.Annotation
	lib.ReadJSONFile(annotationFname, &annotations)
	var testRegions []string
	lib.ReadJSONFile(testFname, &testRegions)
	testSet := make(map[string]bool)
	for _, region := range testRegions {
		testSet[region] = true
	}

	type Item struct {
		Index int
		Annotation lib.Annotation
	}

	// group annotations by label
	groups := make(map[string][]Item)
	for annotationIdx, annotation := range annotations {
		if !testSet[annotation.Cluster.Region] {
			continue
		}
		if annotation.HasTag("nochange") {
			continue
		}
		label := annotation.Cluster.Label()
		groups[label] = append(groups[label], Item{annotationIdx, annotation})
	}
	log.Println("got", len(groups), "groups")

	// fetch JPGs and graphs in a group and call visualize for each annotation
	getJPG := func(label string, suffixes []string) [][][3]uint8 {
		for _, suffix := range suffixes {
			fname := filepath.Join(jpgDir, label+suffix)
			if _, err := os.Stat(fname); os.IsNotExist(err) {
				continue
			}
			return image.ReadImage(fname)
		}
		panic(fmt.Errorf("no image found for %s and %v", label, suffixes))
	}
	process := func(label string) {
		log.Println(label)
		newSuffixes := []string{"_2019.jpg", "_2018.jpg"}
		oldSuffixes := []string{"_2012.jpg", "_2013.jpg"}
		newIm := getJPG(label, newSuffixes)
		oldIm := getJPG(label, oldSuffixes)
		newGraph := lib.ReadGraph(filepath.Join(graphDir, label+"_2020-07-01.graph")).GridIndex(128)
		oldGraph := lib.ReadGraph(filepath.Join(graphDir, label+"_2013-07-01.graph")).GridIndex(128)
		extraGraph := lib.ReadGraph(filepath.Join(graphDir, label+"_2020-07-01_extra.graph")).GridIndex(128)

		for _, item := range groups[label] {
			inferredGraphs := make([]*common.Graph, len(inferredDirs))
			for i, inferredDir := range inferredDirs {
				inferredGraphs[i] = lib.ReadGraph(filepath.Join(inferredDir, fmt.Sprintf("%d.graph", item.Index)))
			}
			outPrefix := filepath.Join(outDir, fmt.Sprintf("%d_", item.Index))
			visualize(item.Annotation, oldIm, newIm, oldGraph, newGraph, extraGraph, inferredGraphs, outPrefix)
		}
	}

	ch := make(chan string)
	var wg sync.WaitGroup
	for i := 0; i < 24; i++ {
		wg.Add(1)
		go func() {
			for label := range ch {
				process(label)
			}
			wg.Done()
		}()
	}
	for label := range groups {
		ch <- label
	}
	close(ch)
	wg.Wait()
}
