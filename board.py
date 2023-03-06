import random, math
from utils import *

class Tile:
	
	def __init__(self, passable, symbol, stair=False):
		self.passable = passable
		assert len(symbol) == 1, "Symbol must be exactly one character"
		self.symbol = symbol
		self.revealed = False
		self.walked = False
		self.stair = stair
		self.items = []

class Board:
	
	def __init__(self, g, cols, rows):
		self.g = g
		self.cols = cols
		self.rows = rows
		self.data = [[Tile(True, " ") for x in range(cols)] for y in range(rows)]
		self.clear_cache()
		
	def clear_cache(self):
		self.collision_cache = [[False for x in range(self.cols)] for y in range(self.rows)]
		
	def line_between(self, pos1, pos2, skipfirst=False, skiplast=False):
		x1, y1 = pos1
		x2, y2 = pos2
		dx = abs(x2 - x1)
		sx = 1 if x1 < x2 else -1
		dy = -abs(y2 - y1)
		sy = 1 if y1 < y2 else -1
		error = dx + dy
		while True:
			doyield = True
			if (skipfirst and (x1, y1) == pos1) or (skiplast and (x1, y1) == pos2):
				doyield = False
			if doyield:
				yield (x1, y1)
			if (x1, y1) == (x2, y2):
				return
			e2 = 2 * error
			if e2 >= dy:
				if x1 == x2:
					return
				error += dy
				x1 += sx
			if e2 <= dx:
				if y1 == y2:
					return 
				error += dx
				y1 += sy
	
	def in_bounds(self, x, y):
		return 0 <= x < self.cols and 0 <= y < self.rows
				
	def line_of_sight(self, pos1, pos2):
		for point in self.line_between(pos1, pos2, skiplast=True):
			if self.blocks_sight(*point):
				return False
		return True
		
	def is_clear_path(self, pos1, pos2):
		for point in self.line_between(pos1, pos2, skipfirst=True, skiplast=True):
			if not self.is_passable(*point):
				return False
		return True
	
	def get_in_radius(self, pos, radius):
		x, y = pos
		for px in range(x-radius, x+radius+1):
			for py in range(y-radius, y+radius+1):
				if (px, py) != pos and self.in_bounds(x, y):
					yield (px, py)
					
	def get_in_circle(self, pos, radius):
		cx, cy = pos
		for x, y in self.get_in_radius(pos, radius):
			dx = x - cx
			dy = y - cy
			dist = math.sqrt(dx**2 + dy**2)
			if round(dist) > radius or not self.in_bounds(x, y):
				continue	
			yield x, y
	
	def get_in_cone(self, pos, radius, angle, widthdeg=60):
		cx, cy = pos 
		angle %= 360
		for x, y in self.get_in_radius(pos, radius):
			dx = x - cx
			dy = y - cy
			dist = math.sqrt(dx**2 + dy**2)
			if round(dist) > radius:
				continue
			dir = math.degrees(math.atan2(dy, dx))
			half = widthdeg/2
			if dir < 0:
				dir += 360
			
			if abs(angle - dir) <= half:
				yield x, y
			elif angle + half >= 360 and dir <= (angle + half) % 360:
				yield x, y 
			elif angle - half < 0 and dir >= angle-half+360:
				yield x, y
		
	#A monster collision cache is used to improve the performance of detecting collisions with monsters
	#This way, checking if there's a monster at a position can be O(1) instead of O(m)
	
	def set_cache(self, x, y):
		self.collision_cache[y][x] = True
		
	def unset_cache(self, x, y):
		self.collision_cache[y][x] = False
			
	def get_cache(self, x, y):
		return self.collision_cache[y][x]
		
	def swap_cache(self, pos1, pos2):
		x1, y1 = pos1
		x2, y2 = pos2
		tmp = self.collision_cache[y1][x1]
		self.collision_cache[y1][x1] = self.collision_cache[y2][x2]
		self.collision_cache[y2][x2] = tmp
	
	def blocks_sight(self, col, row):
		if (col, row) == (self.g.player.x, self.g.player.y):
			return False
		return not self.get(col, row).passable
	
	def is_passable(self, col, row):
		if self.blocks_sight(col, row):
			return False
		return not self.collision_cache[row][col]
		
	def generate(self):
		self.data = [[Tile(False, "#") for x in range(self.cols)] for y in range(self.rows)]
		self.clear_cache()
		WIDTH_RANGE = (5, 10)
		HEIGHT_RANGE = (3, 5)
		ATTEMPTS = 100
		NUM = random.randint(5, 8)
		rooms = []
		randchance = dice(2, 10)
		if one_in(7):
			randchance = 100
		for i in range(NUM):
			for _ in range(ATTEMPTS):
				width = random.randint(*WIDTH_RANGE)
				height = random.randint(*HEIGHT_RANGE)
				xpos = random.randint(1, self.cols - width - 1)
				ypos = random.randint(1, self.rows - height - 1)
				for x, y, w, h in rooms:
					flag = True
					if x + w < xpos or xpos + width < x:
						flag = False
					elif y + h < ypos or ypos + height < y:
						flag = False
					if flag:
						break
				else:
					for x in range(width):
						for y in range(height):
							self.carve_at(xpos + x, ypos + y)
					if i > 0:
						prev = rooms[-1]
						if random.randint(1, randchance) == 1:
							prev = random.choice(rooms)
						x, y, w, h = prev
						pos1_x = x + random.randint(1, w - 2)
						pos1_y = y + random.randint(1, h - 2)
						pos2_x = xpos + random.randint(1, width - 2)
						pos2_y = ypos + random.randint(1, height - 2)
						dx = 1 if pos1_x < pos2_x else -1
						dy = 1 if pos1_y < pos2_y else -1
						if one_in(2):
							x = pos1_x
							while x != pos2_x:
								self.carve_at(x, pos1_y)
								x += dx	
							y = pos1_y
							while y != pos2_y:
								self.carve_at(pos2_x, y)
								y += dy
						else:
							y = pos1_y
							while y != pos2_y:
								self.carve_at(pos1_x, y)
								y += dy
							x = pos1_x
							while x != pos2_x:
								self.carve_at(x, pos2_y)
								x += dx
						
					rooms.append((xpos, ypos, width, height))
					break
							
	def carve_at(self, col, row):
		if not (0 <= col < self.cols and 0 <= row < self.rows):
			raise ValueError(f"carve_at coordinate out of range: ({col}, {row})")
		self.data[row][col] = Tile(True, " ")
		
	def get(self, col, row):
		return self.data[row][col]
		
###############
#Pathfinding
#Algorithm used is A* Search
from collections import defaultdict

class OpenSet:
	
	def __init__(self, key=None):
		self._data = []
		self._dup = set()
		self.key = key or (lambda v: v)
		
	def add(self, value):
		if value in self._dup:
			return
		self._dup.add(value)
		a = self._data
		key = self.key
		i = len(a)
		a.append(value)
		while i > 0:
			parent = i // 2
			if key(a[parent]) < key(a[i]):
				break
			a[parent], a[i] = a[i], a[parent]
			i = parent
			
	def pop(self):
		if len(self._data) == 0:
			raise IndexError("pop from an empty heap")
		a = self._data
		val = a[0]
		a[0] = a[-1]
		a.pop()
		key = self.key
		i = 0
		while True:
			left = 2 * i + 1
			right = 2 * i + 2
			if left >= len(a):
				break
			node = left
			if right < len(a) and key(a[right]) < key(a[left]):
				node = right
			if key(a[i]) > key(a[node]):
				a[i], a[node] = a[node], a[i]
				i = node
			else:
				break
		self._dup.remove(val)
		return val
		
	def __contains__(self, value):
		return value in self._dup
		
	def __bool__(self):
		return len(self._data) > 0
		
def pathfind(board, start, end, rand=False):
	#Actual A* Search algorithm
	def h(a, b):
		return abs(a[0] - b[0]) + abs(a[1] - b[1])
	gScore = defaultdict(lambda: float("inf"))
	gScore[start] = 0
	fScore = defaultdict(lambda: float("inf"))
	fScore[start] = h(start, end)
	open_set = OpenSet(fScore.__getitem__)
	open_set.add(start)
	came_from = {}
	rows = board.rows
	cols = board.cols
	def can_pass(x, y):
		if (x, y) == end:
			return not board.blocks_sight(x, y)
		return board.is_passable(x, y)
	while open_set:
		curr = open_set.pop()
		if curr == end:
			path = [curr]
			while curr in came_from:
				curr = came_from[curr]
				path.append(curr)
			path.reverse()
			return path
		neighbors = []
		x, y = curr
		if x + 1 < cols and can_pass(x + 1, y): 
			neighbors.append((x + 1, y))
		if x - 1 >= 0 and can_pass(x - 1, y): 
			neighbors.append((x - 1, y))
		if y + 1 < rows and can_pass(x, y + 1): 
			neighbors.append((x, y + 1))
		if y - 1 >= 0 and can_pass(x, y - 1):
			neighbors.append((x, y - 1))
		if rand:
			random.shuffle(neighbors)
		
		for n in neighbors:
			t = gScore[curr] + 1 
			if t < gScore[n]:
				came_from[n] = curr
				gScore[n] = t
				fScore[n] = t + h(n, end)
				
				if n not in open_set:
					open_set.add(n)
	return []

#End pathfinding
###############	