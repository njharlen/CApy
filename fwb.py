import mmap
import numpy as np
import pandas as pd

class FWB:
	def __init__(self, filename, index = None):
		# TODO: check if file exists
		# ...

		# TODO: check if index exists
		if index is None:
			index = filename[0:-1] + "i"

		f = open(filename, "rb")
		self.mapped_fwb = mmap.mmap(f.fileno(), 0, prot = mmap.PROT_READ)
		f.close()

		self.fwi = pd.read_csv(index, sep = "\t", names = ["chr", "start", "end"], index_col = "chr")
		self.fwi["cum_offset"] = np.cumsum(np.r_[0, (self.fwi["end"] - self.fwi["start"] + 1)[1:]])

		# TODO: check that index is compatible with filelength (and track width)
		# TODO: other index checks:
		# * no overlapping intervals

		# sort to allow for binary search within a chromosome
		self.fwi = self.fwi.groupby("chr").apply(lambda x : x.sort_values("start")).droplevel(0)

		# TODO: needs to be inferred or specified
		self.width = 16

		self.nullval = -1

	def _get_offset(self, chr, pos):
		"""
		Returns non-width adjusted offset into FWB. Returns -1 for positions that
		are out of range.
		"""

		pos = np.r_[pos]
		C = self.fwi.loc[chr]

		idx = C["start"].searchsorted(pos + 1) - 1
		nnidx = idx >= 0

		bdy = C.iloc[idx[nnidx]][["start", "end"]].values
		bdyidx = np.full(idx.shape, False)
		bdyidx[nnidx] = (bdy[:, 0] <= pos[nnidx]) & (bdy[:, 1] >= pos[nnidx])

		start_offset = C.iloc[idx[bdyidx]][["start", "cum_offset"]].values
		offset = np.full(idx.shape, -1, dtype = np.int64)
		offset[bdyidx] = start_offset[:, 1] + pos[bdyidx] - start_offset[:, 0]

		return offset

	def get(self, chr, start, end = None): 
		# TODO: currently, we only handle the following use cases:
		#       chr[], start[] (multiple individual quries)
		#       chr, start[] (multiple individual quries on same chromosome)
		# Additional use cases to handle:
		# * chr, start, end (single ranged query)
		# * chr[], start[], end[] (multiple ranged queries)

		# TODO: handle widths < 8

		Q = pd.DataFrame({ "chr" : chr, "start" : np.r_[start] })
		offsets = np.zeros(Q.shape[0], dtype = np.int64)
		bytewidth = self.width//8

		# group by chromosome to make lookups faster
		a = 0
		for _, Qc in Q.groupby("chr"):
			offsets[a:(a + Qc.shape[0])] = self._get_offset(Qc["chr"], Qc["start"])*bytewidth
			a += Qc.shape[0] 
		nzidx = offsets >= 0

		# convert memory map to byte array
		b = b''
		for x in offsets[nzidx]:
			b += self.mapped_fwb[x:(x + self.width//8)]

		ret = np.full(Q.shape[0], self.nullval, dtype = np.dtype("i" + str(bytewidth)))
		ret[nzidx] = np.frombuffer(b, dtype = np.dtype(">i" + str(bytewidth)))

		return ret
