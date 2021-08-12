package lib

// Adapt https://leetcode.com/problems/maximal-rectangle/ to find the biggest rectangles.

import (
	//"fmt"
)

func max(a int, b int) int {
	if a > b {
		return a
	} else {
		return b
	}
}

func intersects(r1 [4]int, r2 [4]int) bool {
	return r1[2] >= r2[0] && r2[2] >= r1[0] && r1[3] >= r2[1] && r2[3] >= r1[1]
}

func rectsize(r [4]int) int {
	return (r[2]-r[0])*(r[3]-r[1])
}

func MaximalRectangles(bad [][]bool, minside int) [][4]int {
	// M[i][j]: number of good pixels above this column at this cell
	M := make([][]int, len(bad))
	for i := range bad {
		M[i] = make([]int, len(bad[i]))
	}
	for j := range bad[0] {
		var count int
		for i := range bad {
			if !bad[i][j] {
				count++
			} else {
				count = 0
			}
			M[i][j] = count
		}
	}

	// now, count up # columns with height for rectangles where bottom is at each row
	// then we can compute area at each height from that
	rects := make(map[int][4]int)
	var nextID int = 0
	for i := range M {
		cur := largestRectangleArea(i, M[i], minside)

		for _, r1 := range cur {
			// are we bigger than each existing rect that we intersect with?
			isBigger := true
			for _, r2 := range rects {
				if !intersects(r1, r2) {
					continue
				}
				if rectsize(r1) > rectsize(r2) {
					continue
				}
				isBigger = false
				break
			}
			if !isBigger {
				continue
			}

			// remove each intersecting rect
			for id, r2 := range rects {
				if !intersects(r1, r2) {
					continue
				}
				delete(rects, id)
			}

			rects[nextID] = r1
			nextID++
		}
	}

	var rectList [][4]int
	for _, rect := range rects {
		rectList = append(rectList, rect)
	}
	return rectList
}

func largestRectangleArea(xOffset int, heights []int, minside int) [][4]int {
	// the stack will keep lower heights at indexes prior to the current index
	// since height h at j<i implies larger heights at indexes less than j are irrelevant,
	//	we make sure the stack is always non-decreasing
	// if heights[i] is less than stack[-1] (which came from index j), then we try to make a rectangle
	//	starting at index j of height stack[-1], since that rectangle can have maximal width of 1
	// similarly, if heights[i] is less than stack[-2], we can try to make rectangle there too, which
	//	will have maximal width of 2, and so on
	var stack [][2]int
	var rects [][4]int
	popUntil := func(h int, yOffset int) int {
		// pop all the heights in the stack until remaining heights are <= h
		// each time we pop, we try to form a rectangle that starts at that index
		numPopped := 0
		for len(stack) > 0 {
			cur := stack[len(stack)-1]
			curHeight := cur[0]
			curCount := cur[1]
			if curHeight <= h {
				break
			}
			numPopped += curCount
			stack = stack[0:len(stack)-1]

			if curHeight < minside || numPopped < minside {
				// current rectangle is too small, let's keep going
				continue
			}

			rect := [4]int{xOffset-curHeight+1, yOffset-numPopped, xOffset+1, yOffset}
			for {
				if len(rects) == 0 || !intersects(rect, rects[len(rects)-1]) {
					// no intersection, we can just add this rect
					rects = append(rects, rect)
					break
				}
				if rectsize(rects[len(rects)-1]) > rectsize(rect) {
					// previous intersecting rectangle is bigger, let's keep it instead
					break
				}
				// we are bigger than previous intersecting rectangle, so remove it
				rects = rects[0:len(rects)-1]
			}
		}
		return numPopped
	}
	for yOffset, h := range heights {
		count := popUntil(h, yOffset)
		// count is the number of immediately preceding bars that have at least height h
		stack = append(stack, [2]int{h, count+1})
	}
	popUntil(-1, len(heights))
	return rects
}
