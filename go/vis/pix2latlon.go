package main

import (
	"github.com/favyen/muno21/go/lib"
	"github.com/mitroadmaps/gomapinfer/common"

	"fmt"
	"os"
	"strconv"
)

// Convert a pixel position in a tile to a latitude-longitude coordinate.
// Note: we output LATITUDE (Y AXIS) first so it can be pasted into Google Maps.
// But input is x then y.

func main() {
	region := os.Args[1]
	tileCol, _ := strconv.Atoi(os.Args[2])
	tileRow, _ := strconv.Atoi(os.Args[3])
	x, _ := strconv.Atoi(os.Args[4])
	y, _ := strconv.Atoi(os.Args[5])

	var sizes map[string][2]int
	lib.ReadJSONFile("sizes.json", &sizes)

	label := fmt.Sprintf("%s_%d_%d", region, tileCol, tileRow)
	dims := sizes[label]

	regionObj := lib.GetRegion(region)
	start := regionObj.Start.Add(common.Point{0.1*float64(tileCol), 0.1*float64(tileRow)})
	end := regionObj.Start.Add(common.Point{0.1*float64(tileCol+1), 0.1*float64(tileRow+1)})
	lon := float64(x) * (end.X - start.X) / float64(dims[0]) + start.X
	lat := end.Y - float64(y) * (end.Y - start.Y) / float64(dims[1])
	fmt.Printf("%v, %v\n", lat, lon)
}
