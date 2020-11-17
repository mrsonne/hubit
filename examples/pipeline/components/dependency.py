
class CalculationClass(object):

	def __init__(self):
		self._prices = {'pvdf': 10, 'xlpe': 1.5, 'hdpe': 1, 'pa11': 7}

	
	def price_seg(self, mats, ts, ods, length):
		return length*sum([self._prices[mat]*t*3.14*od for mat, t, od in zip(mats, ts, ods)])
