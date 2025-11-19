from .params import *

def byteops_load_32(x):
	r = x[0] | (x[1] << 8) | (x[2] << 16) | (x[3] << 24)
	return np.uint32(r)

def byteops_load_24(x):
	r = x[0] | (x[1] << 8) | (x[2] << 16)
	return np.uint32(r)

def byteops_cbd(buf, paramsK):
	r = np.zeros(paramsPolyBytes, dtype=np.int16)
	if paramsK == 2:
		for i in range(paramsN//4): 
			t = byteops_load_24(buf[3*i:])
			d = t & 0x00249249
			d = d + ((t >> 1) & 0x00249249)
			d = d + ((t >> 2) & 0x00249249)
			for j in range(4):
				a = np.int16((d >> (6*j + 0)) & 0x7)
				b = np.int16((d >> (6*j + paramsETAK512)) & 0x7)
				r[4*i+j] = a - b
	else:
		for i in range(paramsN//8):
			t = byteops_load_32(buf[4*i:])
			d = t & 0x55555555
			d = d + ((t >> 1) & 0x55555555)
			for j in range(8):
				a = np.int16((d >> (4*j + 0)) & 0x3)
				b = np.int16((d >> (4*j + paramsETAK768K1024)) & 0x3)
				r[8*i+j] = a - b
	return r

def byteops_montgomery_reduce(a):
	return np.int16((a - np.int32(np.int16(a * np.int32(paramsQInv))) * np.int32(paramsQ)) >> 16)

def byteops_barrett_reduce(a):
	v = np.int16(((np.uint32(1) << 26) + np.uint32(paramsQ//2)) // np.uint32(paramsQ))
	t = np.int16(np.int32(v) * np.int32(a) >> 26)
	t = t * np.int16(paramsQ)
	return a - t

def byteops_c_sub_q(a):
	a = a - np.int16(paramsQ)
	a = a + ((a >> 15) & np.int16(paramsQ))
	return a