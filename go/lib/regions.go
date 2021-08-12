package lib

import (
	"github.com/mitroadmaps/gomapinfer/common"
)

type Region struct {
	// e.g. "denver"
	Name string

	// smallest longitude and latitude
	Start common.Point

	// how many tiles along x and y axes
	Width int
	Height int
}

var Regions = []Region{
	{
		Name: "denver",
		Start: common.Point{-105.047648, 39.655721},
		Width: 2,
		Height: 2,
	},
	{
		Name: "phoenix",
		Start: common.Point{-112.249845,33.363589},
		Width: 2,
		Height: 2,
	},
	{
		Name: "seattle",
		Start: common.Point{-122.207566,47.575112},
		Width: 1,
		Height: 1,
	},
	{
		Name: "vegas",
		Start: common.Point{-115.326310,36.078303},
		Width: 2,
		Height: 2,
	},
	{
		Name: "sanantonio",
		Start: common.Point{-98.660111,29.347343},
		Width: 2,
		Height: 2,
	},
	{
		Name: "austin",
		Start: common.Point{-97.842357,30.200509},
		Width: 2,
		Height: 2,
	},
	{
		Name: "dallas",
		Start: common.Point{-96.997231,32.731023},
		Width: 2,
		Height: 2,
	},
	{
		Name: "houston",
		Start: common.Point{-95.47,29.65},
		Width: 2,
		Height: 2,
	},
	{
		Name: "neworleans",
		Start: common.Point{-90.164685,29.887187},
		Width: 1,
		Height: 1,
	},
	{
		Name: "miami",
		Start: common.Point{-80.383707,25.696962},
		Width: 2,
		Height: 2,
	},
	{
		Name: "atlanta",
		Start: common.Point{-84.49,33.66},
		Width: 2,
		Height: 2,
	},
	{
		Name: "detroit",
		Start: common.Point{-83.13,42.30},
		Width: 2,
		Height: 2,
	},
	{
		Name: "dc",
		Start: common.Point{-77.13,38.80},
		Width: 2,
		Height: 2,
	},
	{
		Name: "baltimore",
		Start: common.Point{-76.77,39.28},
		Width: 2,
		Height: 2,
	},
	{
		Name: "pittsburgh",
		Start: common.Point{-80.10,40.34},
		Width: 2,
		Height: 2,
	},
	{
		Name: "philadelphia",
		Start: common.Point{-75.34,39.92},
		Width: 2,
		Height: 2,
	},
	{
		Name: "boston",
		Start: common.Point{-71.25,42.33},
		Width: 2,
		Height: 2,
	},
	{
		Name: "chicago",
		Start: common.Point{-87.81,41.70},
		Width: 2,
		Height: 2,
	},
	{
		Name: "la",
		Start: common.Point{-118.34,33.95},
		Width: 2,
		Height: 2,
	},
	{
		Name: "sf",
		Start: common.Point{-122.49,37.70},
		Width: 1,
		Height: 1,
	},
	{
		Name: "ny",
		Start: common.Point{-74.07,40.71},
		Width: 2,
		Height: 2,
	},
}

func GetRegion(name string) Region {
	for _, region := range Regions {
		if region.Name == name {
			return region
		}
	}
	return Region{}
}
