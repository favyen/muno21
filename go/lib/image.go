package lib

func Dilate(pix [][]uint8, amount int) {
	commit := func() {
		// make origPix>=128 into 255
		for i := range pix {
			for j := range pix[i] {
				if pix[i][j] >= 128 {
					pix[i][j] = 255
				}
			}
		}
	}
	// horizontal dilation
	for i := range pix {
		for j := range pix[i] {
			if pix[i][j] != 255 {
				continue
			}
			for off := -amount; off <= amount; off++ {
				if i+off < 0 || i+off >= len(pix) {
					continue
				}
				if pix[i+off][j] == 255 {
					continue
				}
				pix[i+off][j] = 128
			}
		}
	}
	commit()
	// vertical dilation
	for i := range pix {
		for j := range pix[i] {
			if pix[i][j] != 255 {
				continue
			}
			for off := -amount; off <= amount; off++ {
				if j+off < 0 || j+off >= len(pix[i]) {
					continue
				}
				if pix[i][j+off] == 255 {
					continue
				}
				pix[i][j+off] = 128
			}
		}
	}
	commit()
}
