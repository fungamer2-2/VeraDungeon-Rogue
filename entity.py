import random
from collections import deque
from board import pathfind

class Entity:
	
	def __init__(self, g):
		self.g = g
		self.x = 0
		self.y = 0
		self.curr_target = None
		self.curr_path = deque()
		self.placed = False
		self.energy = 0 #How many energy points this entity has. Used to control movement speed.
		self.fov = set()
		
	def calc_fov(self):
		"Calculates all tiles an entity can see from the current position"
		board = self.g.board
		fov = set()
		fov.add((self.x, self.y))
		#Raycasting step
		for x in range(board.cols):
			for point in board.line_between((self.x, self.y), (x, 0), skipfirst=True):
				fov.add(point)
				if board.blocks_sight(*point):
					break			
			for point in board.line_between((self.x, self.y), (x, board.rows - 1), skipfirst=True):
				fov.add(point)
				if board.blocks_sight(*point):
					break
		for y in range(1, board.rows - 1):
			for point in board.line_between((self.x, self.y), (0, y), skipfirst=True):
				fov.add(point)
				if board.blocks_sight(*point):
					break
			for point in board.line_between((self.x, self.y), (board.cols - 1, y), skipfirst=True):
				fov.add(point)
				if board.blocks_sight(*point):
					break
					
		#Post-processing step
		seen = set()
		for cell in fov.copy():
			if board.blocks_sight(*cell):
				continue
			x, y = cell
			dx = x - self.x
			dy = y - self.y
			neighbors = {(x-1, y), (x+1, y), (x, y-1), (x, y+1)}
			neighbors -= seen
			neighbors -= fov
			for xp, yp in neighbors:
				seen.add((xp, yp))
				if not (0 <= xp < board.cols):
					continue
				if not (0 <= yp < board.cols):
					continue
				if board.blocks_sight(xp, yp):
					visible = False
					dxp = xp - x
					dyp = yp - y
					if dx <= 0 and dy <= 0:
						visible = dxp <= 0 or dyp <= 0
					if dx >= 0 and dy <= 0:
						visible = dxp >= 0 or dyp <= 0
					if dx <= 0 and dy >= 0:
						visible = dxp <= 0 or dyp >= 0	
					if dx >= 0 and dy >= 0:
						visible = dxp >= 0 or dyp >= 0
					if visible:
						fov.add((xp, yp))
						
		return fov
		
	def can_see(self, x, y):
		return (x, y) in self.fov
		
	def distance(self, other, manhattan=True):
		dx = abs(self.x - other.x)
		dy = abs(self.y - other.y)
		if manhattan:
			return dx + dy
		return max(dx, dy)
		
	def distance_pos(self, pos):
		return abs(self.x - pos[0]) + abs(self.y - pos[1])
		
	def clear_path(self):
		self.curr_path.clear()
		
	def path_towards(self, x, y, maxlen=None):
		if self.curr_target == (x, y) and self.curr_path and self.move_to(*self.curr_path.popleft()):
			if (self.x, self.y) == (x, y):
				self.clear_path()
			return
		path = pathfind(self.g.board, (self.x, self.y), (x, y), rand=True)
		if len(path) < 2:
			return
		if maxlen and len(path) > maxlen+1:
			return
		currX, currY = self.x, self.y
		self.curr_target = (x, y)
		self.curr_path = deque(path[1:])
		newX, newY = self.curr_path.popleft()
		self.move_to(newX, newY)
		
	def set_path(self, path):
		self.curr_path = deque(path)
		
	def can_place(self, x, y):
		if (x, y) == (self.g.player.x, self.g.player.y):
			return False
		board = self.g.board
		if not board.is_passable(x, y):
			return False
		neighbors = [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]
		for xp, yp in neighbors:
			if board.is_passable(xp, yp):
				return True
		return False
		
	def place_randomly(self):
		board = self.g.board
		for _ in range(200):
			x = random.randint(1, board.cols - 2)
			y = random.randint(1, board.rows - 2)
			if self.can_place(x, y):
				break
		else: #We couldn't place the player randomly, so let's search all possible positions in a random order
			row_ind = list(range(1, board.rows - 1))
			random.shuffle(row_ind)
			found = False
			for ypos in row_ind:
				col_ind = list(range(1, board.cols - 1))
				random.shuffle(col_ind)
				for xpos in col_ind:
					if self.can_place(xpos, ypos):
						x, y = xpos, ypos
						found = True
						break
				if found:
					break
			else:
				 return False
		self.place_at(x, y)
		return True
		
	def place_at(self, x, y):
		old = (self.x, self.y)
		self.x = x
		self.y = y
		if self.placed:
			self.g.board.swap_cache(old, (self.x, self.y))
		else:
			self.placed = True
			self.g.board.set_cache(x, y)
		
	def swap_with(self, other):
		tmp = (self.x, self.y)
		self.x, self.y = other.x, other.y
		other.x, other.y = tmp
		
	def move_to(self, x, y):
		board = self.g.board
		if board.is_passable(x, y):
			oldpos = (self.x, self.y)
			self.x = x
			self.y = y
			self.g.board.swap_cache(oldpos, (self.x, self.y))
			return True
		return False
		
	def move(self, dx, dy):
		return self.move_to(self.x + dx, self.y + dy)