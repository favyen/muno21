package main

import (
	"github.com/mitroadmaps/gomapinfer/common"
	"github.com/favyen/muno21/go/lib"

	"fmt"
	"log"
	"path/filepath"
	"os"
	"os/exec"
)

func main() {
	// e.g. us-internal.osh.pbf
	historyFname := os.Args[1]
	outDir := os.Args[2]

	for _, region := range lib.Regions {
		start := region.Start
		size := common.Point{float64(region.Width), float64(region.Height)}
		end := region.Start.Add(size.Scale(0.1))
		outFname := filepath.Join(outDir, region.Name+".pbf")
		if _, err := os.Stat(outFname); err == nil {
			continue
		}
		args := []string{
			"extract", "--bbox",
			fmt.Sprintf("%v,%v,%v,%v", start.X-0.01, start.Y-0.01, end.X+0.01, end.Y+0.01),
			"-H", historyFname,
			"-o", outFname,
		}
		log.Println("osmium", args)
		cmd := exec.Command("osmium", args...)
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		err := cmd.Run()
		if err != nil {
			panic(err)
		}
	}
}
