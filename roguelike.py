try:
	import curses
except:
	print("Sorry, Windows doesn't support the curses module.")
	exit()
	
import random, time, textwrap
import math
from collections import deque
from itertools import islice, chain
from os import get_terminal_size

def dice(num, sides):
	"Rolls a given numver of dice with a given number of dice and takes the sum"
	return sum(random.randint(1, sides) for _ in range(num))

def div_rand(x, y):
	"Computes x/y then randomly rounds the result up or down depending on the remainder"
	sign = 1
	if (x > 0) ^ (y > 0):
		sign = -1
		x = abs(x)
		y = abs(y)
	mod = x % y
	return sign * x//y + (random.randint(1, y) <= mod)

def mult_rand_frac(num, x, y):
	return div_rand(num*x, y)
	
def rand_weighted(*pairs):
	names, weights = list(zip(*pairs))
	return random.choices(names, weights=weights)[0]

def to_hit_prob(AC, hit_mod=0, adv=False, disadv=False):
	"""
	Calculates the percentage chance of successfully landing a hit
	adv - If true, calculates the probability with advantage
	disadv - If true, calculates the probability with disadvantage
	"""
	if adv and disadv:
		adv = False
		disadv = False
	num_over = max(1, min(21 - AC + hit_mod, 19))
	res = num_over/20
	if adv:
		res = 1-((1 - res)**2)
	elif disadv:
		res = res**2
	return round(res, 3)
	
def calc_mod(stat, avg=False):
	m = stat - 10
	if avg:
		return m / 2
	else:
		return div_rand(m, 2)
	
def display_prob(perc):
	if perc <= 0:
		return "0%"
	if perc >= 100:
		return "100%"
	if perc <= 0.5:
		return "<1%"
	if perc >= 99.5:
		return ">99%"
	if perc < 50:
		perc = math.ceil(perc - 0.5)
	else:
		perc = math.floor(perc + 0.5)
	return f"{perc}%"

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
		if random.randint(1, 7) == 1:
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
						if random.randint(1, 2) == 1:
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
	
class Game:
		
	def __init__(self):
		self.screen = curses.initscr()
		curses.start_color()
		
		curses.init_pair(1, curses.COLOR_RED, 0)
		curses.init_pair(2, curses.COLOR_GREEN, 0)
		curses.init_pair(3, curses.COLOR_YELLOW, 0)
		curses.init_pair(4, curses.COLOR_BLUE, 0)
		
		self.screen.clear()
		curses.noecho()
		self.board = Board(self, 40, 16)
		self.player = Player(self)
		self.monsters = []
		self.msg_list = deque(maxlen=50)
		self.msg_cursor = 0
		self.projectile = None
		self.level = 1
		types = Effect.__subclasses__()
		self.effect_types = {t.name:t for t in types}
	
	def help_menu(self):
		size = get_terminal_size()
		termwidth = size.columns
		msg = []
		def add_text(txt=""):
			nonlocal msg
			txt = str(txt)
			msg += textwrap.wrap(txt, termwidth)
		def add_line():
			msg.append("")
			
		add_text("Use the wasd keys to move")
		add_text("Use the q and z keys to scroll the message log")
		add_text("f - view info about monsters currently in view")
		add_text("r - rest until HP is recovered")
		add_text("p - pick up item")
		add_text("u - use item")
		add_text("space - go down to next level (when standing on a \">\" symbol)")
		add_text("? - brings up this menu again")
		add_text(". - wait a turn")
		add_text("j - view item descriptions at this tile")
		add_line()
		add_text("Press enter to continue")
		screen = self.screen
		screen.clear()
		screen.addstr(0, 0, "\n".join(msg))
		screen.refresh()
		while screen.getch() != 10: pass
		self.draw_board()
		
	def game_over(self):
		size = get_terminal_size()
		termwidth = size.columns
		msg = []
		def add_text(txt=""):
			nonlocal msg
			txt = str(txt)
			msg += textwrap.wrap(txt, termwidth)
		def add_line():
			msg.append("")
			
		p = self.player
		add_text("GAME OVER")
		add_line()
		add_text(f"You reached Dungeon Level {self.level}")
		add_text(f"You attained XP level {p.level}")
		add_line()
		add_line(f"Your final stats were:")
		add_text(f"STR {p.STR}, DEX {p.DEX}")
		add_line()
		add_text("Press enter to quit")
		screen = self.screen
		screen.clear()
		screen.addstr(0, 0, "\n".join(msg))
		screen.refresh()
		while screen.getch() != 10: pass
			
	def set_projectile_pos(self, x, y):
		self.projectile = (x, y)
	
	def clear_projectile(self):
		self.projectile = None
		
	def input(self, message=None):
		if message:
			self.print_msg(message)
		self.draw_board()
		curses.echo()
		string = self.screen.getstr()
		curses.noecho()
		self.draw_board()
		return string.decode()
		
	def add_monster(self, m):
		if m.place_randomly():
			self.monsters.append(m)
	
	def generate_level(self):
		self.monsters.clear()
		self.board.generate()
		self.player.rand_place()
		self.player.fov = self.player.calc_fov()
		num = random.randint(3, 4) + random.randint(0, int(1.4*(self.level - 1)**0.65))
		monsters = Monster.__subclasses__()
		for _ in range(num):
			tries = 0
			while True:
				typ = random.choice(monsters)
				if self.level > int((typ.min_level - 1)*random.uniform(1, 1.7)):
					break
				tries += 1
				if tries >= 500:
					break
			m = typ(self)
			if m.place_randomly():
				if random.randint(1, 2) == 1:
					fov = self.player.fov
					los_tries = 100
					while los_tries > 0:
						if (m.x, m.y) not in fov:
							break
						m.place_randomly()
						los_tries -= 1
				self.monsters.append(m)
		
		def place_item(typ):
			for j in range(200):
				x = random.randint(1, self.board.cols - 2)
				y = random.randint(1, self.board.rows - 2)
				if self.board.is_passable(x, y):
					tile = self.board.get(x, y)
					if not tile.items:
						tile.items.append(typ())
						break
							
		if random.randint(1, 5) < 5:
			potential = []
			if random.randint(1, 2) == 1:
				potential.append(HealthPotion)
			if random.randint(1, 4) == 1:
				potential.append(ResistPotion)
			if random.randint(1, 5) == 1:
				potential.append(SpeedPotion)
			if random.randint(1, 6) == 1:		
				potential.append(InvisibilityPotion)
			for p in potential:
				if random.randint(1, 100) <= 70:
					place_item(p)
		if random.randint(1, 100) <= 35:
			typ = rand_weighted(
				(TeleportScroll, 1),
				(SleepScroll, 1),
				(ConfusionScroll, 2)
			)
			place_item(typ)
		self.draw_board()
		self.refresh_cache()
	
	def monster_at(self, x, y):
		if (x, y) == (self.player.x, self.player.y):
			return False
		return self.board.get_cache(x, y)
		
	def get_monster(self, x, y):
		if not self.monster_at(x, y):
			return None
		return next((mon for mon in self.monsters if (mon.x, mon.y) == (x, y)), None)
		
	def remove_monster(self, m):
		try:
			ind = self.monsters.index(m)
		except ValueError:
			pass
		else:
			del self.monsters[ind]
			self.board.unset_cache(m.x, m.y)
	
	def print_msg_if_sees(self, pos, msg, color=None):
		assert len(pos) == 2 and type(pos) == tuple
		if pos in self.player.fov:
			self.print_msg(msg, color=None)
			
	def print_msg(self, msg, color=None):
		m = {
			"red": 1,
			"green": 2,
			"yellow": 3
		}
		color = m.get(color, 0)
		size = get_terminal_size()
		termwidth = size.columns
		for line in str(msg).splitlines():
			self.msg_list.extend(map(lambda s: (s, color), textwrap.wrap(line, termwidth)))
		self.msg_cursor = max(0, len(self.msg_list) - self.get_max_lines())
		
	def get_max_lines(self):
		return min(8, get_terminal_size().lines - (self.board.rows + 2))
		
	def draw_board(self):
		screen = self.screen
		board = self.board
		screen.clear()
		p = self.player
		screen.addstr(0, 0, f"HP {p.HP}/{p.MAX_HP} | DG. LV {self.level} | XP {p.exp}/{p.max_exp()} ({p.level})")
		fov = self.player.fov
		for point in fov:
			board.get(*point).revealed = True
		offset = 1
		for row in range(board.rows):
			for col in range(board.cols):
				tile = board.get(col, row)
				if not tile.revealed:
					continue
				s = tile.symbol
				color = 0
				if (col, row) == (self.player.x, self.player.y):
					s = "P"
					if not self.player.has_effect("Invisible"):
						color = curses.A_REVERSE
					else:
						color = curses.color_pair(4)
				elif tile.items:
					item = tile.items[-1]
					s = item.symbol
					color = curses.color_pair(2)
					if isinstance(item, Scroll):
						color = curses.color_pair(4) | curses.A_BOLD
				elif tile.symbol == " ":
					if (col, row) in fov:
						s = "."
					if self.projectile:
						x, y = self.projectile
						if (col, row) == (x, y):
							s = "*"
				try:
					screen.addstr(row + offset, col, s, color)
				except curses.error:
					pass
		for m in self.monsters:
			x, y = m.x, m.y
			if (x, y) in fov:
				color = curses.color_pair(3) if m.ranged else 0
				if m.has_effect("Confused"):
					color = curses.color_pair(4)
				elif not m.is_aware:
					if m.has_effect("Asleep"):
						color = curses.color_pair(4)
					color |= curses.A_REVERSE
				try:
					screen.addstr(y+offset, x, m.symbol, color)
				except curses.error:
					pass
		width = get_terminal_size().columns
		max_lines = self.get_max_lines()
		messages = list(islice(self.msg_list, self.msg_cursor, self.msg_cursor+self.get_max_lines()))
		for i, msg in enumerate(messages):
			message, color = msg
			c = curses.color_pair(color)
			if color == 1:
				c |= curses.A_BOLD
			if i == len(messages) - 1 and self.msg_cursor < max(0, len(self.msg_list) - self.get_max_lines()):
				message += " (↓)"
			try:
				screen.addstr(board.rows + i + offset + 1, 0, message, c)
			except:
				pass
		wd = min(width, 60)
		str_string = f"STR {self.player.STR}"
		screen.addstr(0, wd - len(str_string), str_string)
		dex_string = f"DEX {self.player.DEX}"
		screen.addstr(1, wd - len(dex_string), dex_string)
		
		try:
			screen.move(board.rows + offset, 0)
		except curses.error:
			pass
		screen.refresh()
		
	def refresh_cache(self):
		"Refreshes the monster collision cache"
		board = self.board
		board.clear_cache()
		board.set_cache(self.player.x, self.player.y)
		for m in self.monsters[:]:
			board.set_cache(m.x, m.y)  
		
	def do_turn(self):
		while self.player.energy <= 0:
			if random.randint(1, 6) == 1: #In case anything goes wrong, refresh the monster collision cache every so often
				self.refresh_cache()
			self.player.do_turn()
			order = self.monsters[:]
			random.shuffle(order)
			order.sort(key=lambda m: m.speed, reverse=True)
			for m in order:
				if m.HP > 0:
					m.do_turn()
					if self.player.dead:
						return
				else:
					self.monsters.remove(m)
			self.player.energy += self.player.get_speed()
				

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
		
	def path_towards(self, x, y):
		if self.curr_target == (x, y) and self.curr_path and self.move_to(*self.curr_path.popleft()):
			if (self.x, self.y) == (x, y):
				self.curr_path.clear()
			return
		path = pathfind(self.g.board, (self.x, self.y), (x, y), rand=True)
		if len(path) < 2:
			return
		self.curr_target = (x, y)
		self.curr_path = deque(path[1:])
		self.move_to(*self.curr_path.popleft())
		
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
		old = (self.x, self.y)
		self.x = x
		self.y = y
		if self.placed:
			self.g.board.swap_cache(old, (self.x, self.y))
		else:
			self.placed = True
			self.g.board.set_cache(x, y)
		return True
		
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

class Effect:
	name = "Generic Effect"
	
	def __init__(self, duration, add_msg, rem_msg):
		self.duration = duration
		self.add_msg = add_msg
		self.rem_msg = rem_msg
		
	def on_expire(self, player):
		pass
		
class Haste(Effect):
	name = "Haste"
	
	def __init__(self, duration):
		super().__init__(duration, "You begin to move faster.", "Your extra speed runs out.")
	
	def on_expire(self, player):
		g = player.g
		g.print_msg("A wave of lethargy sweeps over you.")
		player.energy -= g.player.get_speed()

class Resistance(Effect):
	name = "Resistance"
	
	def __init__(self, duration):
		super().__init__(duration, "You feel more resistant to damage.", "You feel vulnerable again.")
	
class Invisible(Effect):
	name = "Invisible"
	
	def __init__(self, duration):
		super().__init__(duration, "You become invisible.", "You become visible again.")
		
class Item:
	description = "This is a generic item that does nothing special. If you see this, it's a bug."
	
	def __init__(self, name, symbol):
		self.name = name
		self.symbol = symbol
		
	def use(self, player):
		g = player.g
		g.print_msg("You use an item. Nothing interesting seems to happen")
		return True
		
class Scroll(Item):
	description = "This is a regular scroll that does nothing. If you see this, it's a bug."
	
	def __init__(self, name):
		super().__init__(name, "@")
		
	def use(self, player):
		g = player.g
		g.print_msg("You look at the blank scroll. It crumbles to dust immediately because it's so useless.")
		return True

class HealthPotion(Item):
	description = "Consuming this potions increases the HP of the one who drinks it."
	
	def __init__(self):
		super().__init__("health potion", "P")
		
	def use(self, player):
		g = player.g
		if player.HP >= player.MAX_HP:
			g.print_msg("Your HP is already full!")
			return False
		else:
			recover = 10 + random.randint(0, player.MAX_HP//4) + random.randint(0, player.MAX_HP//4)
			g.print_msg("You recover some HP.")
			player.HP = min(player.MAX_HP, player.HP + recover)
			return True
			
class SpeedPotion(Item):
	description = "Consuming this potion temporarily speeds the movement of the one who drinks it. However, once the effect wears off, they won't be able to move for a turn, as a wave of lethargy passes over them."
	
	def __init__(self):
		super().__init__("speed potion", "S")
		
	def use(self, player):
		g = player.g
		g.print_msg("You drink a speed potion.")
		if player.has_effect("Haste"):
			g.print_msg("Your speed begins to last even longer.")
		player.gain_effect("Haste", random.randint(30, 45))
		return True
		
class ResistPotion(Item):	
	description = "Consuming this potion temporarily halves all damage taken by the one who drinks it."
	
	def __init__(self):
		super().__init__("resistance potion", "R")
		
	def use(self, player):
		g = player.g
		g.print_msg("You drink a resistance potion.")
		if player.has_effect("Resistance"):
			g.print_msg("Your resistance begins to last even longer.")
		player.gain_effect("Resistance", random.randint(30, 45))
		return True
		
class InvisibilityPotion(Item):
	description = "Consuming this potion makes the one who drinks it temporarily invisible. However, attacking a monster will reduce the duration of this effect."
	
	def __init__(self):
		super().__init__("invisibility potion", "C")
		
	def use(self, player):
		g = player.g
		g.print_msg("You drink an invisibility potion.")
		if player.has_effect("Invisible"):
			g.print_msg("Your invisibility begins to last even longer.")
		player.gain_effect("Invisible", random.randint(45, 60))
		return True
		
class ConfusionScroll(Scroll):
	description = "Reading this scroll may cause nearby monsters to become confused."
	
	def __init__(self):
		super().__init__("scroll of confusion")
	
	def use(self, player):
		g = player.g
		g.print_msg("You read a scroll of confusion. The scroll crumbles to dust.")
		for m in player.monsters_in_fov():
			if dice(1, 20) + calc_mod(m.WIS) >= 15:
				g.print_msg(f"The {m.name} resists.")
			else:
				g.print_msg(f"The {m.name} is confused!")
				m.gain_effect("Confused", random.randint(30, 45))
		return True
		
class SleepScroll(Scroll):
	description = "Reading this scroll may cause some of the nearby monsters to fall asleep."
	
	def __init__(self):
		super().__init__("scroll of sleep")
	
	def use(self, player):
		g = player.g
		g.print_msg("You read a scroll of sleep. The scroll crumbles to dust.")
		mons = list(player.monsters_in_fov())
		random.shuffle(mons)
		mons.sort(key=lambda m: m.HP)
		power = dice(10, 8)
		to_affect = []
		for m in mons:
			if m.has_effect("Asleep"):
				continue
			power -= m.HP
			if power < 0:
				break
			to_affect.append(m)
		if to_affect:
			random.shuffle(to_affect)
			for m in to_affect:
				g.print_msg(f"The {m.name} falls asleep!")
				m.gain_effect("Asleep", random.randint(30, 45))
				m.is_aware = False
		else:
			g.print_msg("Nothing seems to happen.")
		return True
		
class TeleportScroll(Scroll):
	description = "Reading this scroll will randomly teleport the one who reads it."
	
	def __init__(self):
		super().__init__("scroll of teleportation")
	
	def use(self, player):
		g = player.g
		g.print_msg("You read a scroll of teleportation. The scroll crumbles to dust.")
		player.teleport()
		player.energy -= player.get_speed()
		return True
			
class Player(Entity):
	
	def __init__(self, g):
		super().__init__(g)
		self.MAX_HP = 100
		self.HP = 100
		self.dead = False
		self.ticks = 0
		self.resting = False
		self.inventory = []
		self.exp = 0
		self.level = 1
		self.energy = 30
		self.speed = 30
		self.STR = 10
		self.DEX = 10
		self.effects = {}
		self.did_attack = False
		
	def get_ac_bonus(self, avg=False):
		s = calc_mod(self.DEX, avg)
		if self.has_effect("Haste"):
			s += 2
		return s
		
	def get_speed(self):
		speed = self.speed
		if self.has_effect("Haste"):
			speed *= 2
		return int(speed)
		
	def max_exp(self):
		return 40 + (self.level - 1) * 10
		
	def gain_exp(self, amount):
		self.exp += amount
		old_level = self.level
		while self.exp >= self.max_exp():
			self.exp -= self.max_exp()
			self.level += 1
			if self.level % 2 == 0:		
				if random.randint(1, 2) == 1:	
					self.STR += 1
				else:
					self.DEX += 1
			if self.level % 3 == 0:
				self.g.print_msg(f"You leveled up to level {(self.level)}!", "green")
				old_level = self.level
				while True:
					user = self.g.input("Would you like to increase (S)TR or (D)EX?")
					user = user.upper()
					if user == "S":
						self.STR += 1
						break
					elif user == "D":
						self.DEX += 1
						break
					else:
						self.g.print_msg("Please enter \"S\" or \"D\"")
						
		if self.level > old_level:
			self.g.print_msg(f"You leveled up to level {(self.level)}!", "green")
			self.MAX_HP = 100 + (self.level - 1)*15
	
	def take_damage(self, dam):
		if dam <= 0:
			return
		self.HP -= dam
		if self.resting:
			self.g.print_msg("Your rest was interrupted.", "yellow")
			self.resting = False
		if self.HP <= 0:
			self.HP = 0
			self.g.print_msg("You have died!", "red")
			self.dead = True
		elif self.HP <= self.MAX_HP // 4:
			self.g.print_msg("*** WARNING: Your HP is low! ***", "red")

	def rand_place(self):
		self.x = 0
		self.y = 0
		if not super().place_randomly():
			raise RuntimeError("Could not generate a valid starting position for player")
	
	def teleport(self):
		board = self.g.board
		oldloc = (self.x, self.y)
		for _ in range(500):
			x = random.randint(1, board.cols - 2)
			y = random.randint(1, board.rows - 2)
			if board.is_passable(x, y) and (x, y) != oldloc:
				seeslastpos = board.line_of_sight((x, y), oldloc)
				if seeslastpos and random.randint(1, 2) == 1:
					continue
				if not seeslastpos: #We teleported out of sight
					for m in self.monsters_in_fov():
						m.stop_tracking()
				self.g.print_msg("You teleport!")
				self.x = x
				self.y = y
				self.fov = self.calc_fov()
				break
		else:
			self.g.print_msg("You feel yourself begin to teleport, but nothing happens.")
	
	def move(self, dx, dy):
		if self.dead:
			self.energy = 0
			return False
		adj = []
		if (m := self.g.get_monster(self.x-1, self.y)):
			adj.append(m)
		if (m := self.g.get_monster(self.x+1, self.y)):
			adj.append(m)
		if (m := self.g.get_monster(self.x, self.y+1)):
			adj.append(m)
		if (m := self.g.get_monster(self.x, self.y+1)):
			adj.append(m)
		if not super().move(dx, dy):
			if self.g.monster_at(self.x + dx, self.y + dy):
				self.attack(dx, dy)
				return True
			return False
		self.fov = self.calc_fov()
		speed = self.get_speed()
		board = self.g.board
		if dx != 0 or dy != 0:
			tile = board.get(self.x, self.y)
			if not tile.walked:
				tile.walked = True
				if tile.items:
					strings = list(map(lambda item: item.name, tile.items))
					if len(strings) == 1:
						self.g.print_msg(f"You see a {strings[0]} here.")
					else:
						self.g.print_msg(f"At this location you see the following items: {', '.join(strings)}")
		for m in adj:
			dist = abs(self.x - m.x) + abs(self.y - m.y)
			if m.has_effect("Confused"): #Confused monsters can't make opportunity attacks
				continue
			if m.is_aware and m.sees_player() and dist == 2 and (m.speed > speed or (m.speed == speed and random.randint(1, 2) == 1)) and random.randint(1, 3) == 1:
				self.g.print_msg(f"As you move away from {m.name}, it makes an opportunity attack!", "yellow")
				m.melee_attack_player(force=True)
		self.energy -= 30
		return True
		
	def gain_effect(self, name, duration):
		types = self.g.effect_types
		if name in types:
			typ = types[name]
			if name in self.effects:
				self.effects[name].duration += div_rand(duration, 2)
			else:
				self.effects[name] = (eff := typ(duration))
				self.g.print_msg(eff.add_msg)
	
	def has_effect(self, name):
		return name in self.effects
		
	def monsters_in_fov(self):
		for m in self.g.monsters:
			if (m.x, m.y) in self.fov:
				yield m
		
	def adjust_duration(self, effect, amount):
		if effect in self.effects:
			eff = self.effects[effect]
			eff.duration += amount
			if eff.duration <= 0:
				del self.effects[effect]
				self.g.print_msg(eff.rem_msg)
				eff.on_expire(self)
	
	def do_turn(self):	
		if self.HP < self.MAX_HP:
			self.ticks += 1
			if self.ticks % 6 == 0:
				self.HP += 1
		for e in list(self.effects.keys()):
			self.adjust_duration(e, -1)
		mod = 0
		if self.did_attack:
			mod -= 5
		if self.has_effect("Invisible"):
			mod += 5
		for m in self.g.monsters:
			m.check_timer -= 1
			if m.check_timer <= 0 or self.did_attack:
				m.reset_check_timer()
				if not m.is_aware:
					roll = dice(1, 20)
					perc = m.passive_perc
					if m.has_effect("Asleep"):
						perc -= 5
					if (m.x, m.y) in self.fov and (roll == 1 or roll + div_rand(self.DEX - 10, 2) + mod < perc):
						m.is_aware = True
						m.last_seen = (self.x, self.y)
						m.remove_effect("Asleep")
		self.did_attack = False
				
	def attack(self, dx, dy):
		x, y = self.x + dx, self.y + dy
		if not self.g.monster_at(x, y):
			self.g.print_msg("You strike at the air.")
			self.energy -= self.get_speed()
			return
		mon = self.g.get_monster(x, y)
		self.energy -= min(self.get_speed(), 45)
		roll = dice(1, 20)
		sneak_attack = not mon.is_aware
		if sneak_attack:
			roll = max(roll, dice(1, 20))
			self.g.print_msg(f"You catch the {mon.name} completely unaware!")
		elif self.has_effect("Invisible"):
			roll = max(roll, dice(1, 20))
		crit = False
		if roll == 1:
			hits = False
		elif roll == 20:
			hits = True
			crit = dice(1, 20) + calc_mod(self.STR) >= mon.AC
		else:
			hits = roll + calc_mod(self.STR) >= mon.AC
		if mon.has_effect("Asleep"):
			hits = True
			mon.is_aware = True
			mon.remove_effect("Asleep")
		mon.on_player_attacked()
		self.did_attack = True
		self.adjust_duration("Invisible", -random.randint(0, 6))
		if not hits:
			self.g.print_msg(f"Your attack misses the {mon.name}.")
		else:
			dam = dice(1, 6)
			if crit:
				dam += dice(1, 6)
			if sneak_attack:
				#Roll (1+(level-1)/4)d6 bonus damage
				#A non-integer amount of dice, for example, (1.5)d6 is simulated like 1d6 + 0.5*(1d6)
				scale_int = 1 + (self.level - 1) // 4
				scale_mod = (self.level - 1) % 4
				dam += dice(scale_int, 6) + mult_rand_frac(dice(1, 6), scale_mod, 4)
			dam += div_rand(self.STR - 10, 2)
			if dam < 1:
				dam = 1
			mon.HP -= dam
			self.g.print_msg(f"You hit the {mon.name} for {dam} damage.")
			if crit:
				self.g.print_msg("Critical!", "green")
			if mon.HP <= 0:
				self.g.print_msg(f"The {mon.name} dies!", "green")
				self.g.remove_monster(mon)
				lev = mon.diff - 1
				gain = math.ceil(min(6 * 2**lev, 30 * 1.5**lev))
				self.gain_exp(gain)
				if not self.g.monsters:
					if self.g.level == 1:
						self.g.print_msg("Level complete! Move onto the stairs marked with a \">\", then press SPACE to go down to the next level.")
					board = self.g.board
					los_tries = 100
					while True:
						sx = random.randint(1, board.cols - 2)
						sy = random.randint(1, board.rows - 2)
						if not board.is_passable(sx, sy):
							continue
						if los_tries > 0 and board.line_of_sight((self.x, self.y), (sx, sy)):
							los_tries -= 1
							continue
						if abs(self.x - sx) + abs(self.y - sy) <= 4:
							continue
						tile = board.get(sx, sy)
						tile.symbol = ">"
						tile.stair = True
						break
					pass
			else:
				 self.g.print_msg(f"It has {mon.HP} HP")

class Attack:
	
	def __init__(self, dmg, to_hit, msg="The {0} attacks you"):
		self.dmg = dmg
		self.to_hit = to_hit
		self.msg = msg
								
class Monster(Entity):
	min_level = 1
	speed = 30
	diff = 1
	AC = 10
	to_hit = 0
	passive_perc = 11
	WIS = 10
	attacks = [Attack((1, 3), 0)]
	
	def __init__(self, g, name="monster", symbol=None, HP=10, ranged=None, ranged_dam=(2, 3)):
		super().__init__(g)
		if ranged is None:
			ranged = random.randint(1, 5) == 1
		self.HP = HP
		self.MAX_HP = HP
		self.name = name
		self.ranged = ranged
		self.last_seen = None
		self.dir = None
		self._symbol = symbol
		self.ranged_dam = ranged_dam
		self.track_timer = 0
		self.is_aware = False
		self.check_timer = 1
		self.effects = {}
		
	def reset_check_timer(self):
		self.check_timer = random.randint(1, 3)
	
	@property	
	def symbol(self):
		if self._symbol:
			return self._symbol
		return "R" if self.ranged else "&"
	
	def move(self, dx, dy):
		if super().move(dx, dy):
			self.energy -= 30
			return True
		return False
		
	def has_effect(self, name):
		return name in self.effects
		
	def remove_effect(self, name):
		if name in self.effects:
			del self.effects[name]
		
	def gain_effect(self, name, duration):
		if name not in self.effects:
			self.effects[name] = 0
		self.effects[name] += duration
	
	def do_turn(self):
		self.energy += self.speed
		while self.energy > 0:
			old = self.energy
			self.actions()
			if self.energy == old:
				self.energy = min(self.energy, 0) 
		for e in list(self.effects.keys()):
			self.effects[e] -= 1
			if self.effects[e] <= 0:
				del self.effects[e]
			
	def should_use_ranged(self):
		board = self.g.board
		player = self.g.player
		if not board.is_clear_path((self.x, self.y), (player.x, player.y)):
			return False
		return random.randint(1, 100) <= 40
		
	def melee_attack_player(self, attack=None, force=False):
		if attack is None:
			attack = random.choice(self.attacks)
		player = self.g.player
		roll = dice(1, 20)
		if player.has_effect("Invisible"):
			roll = min(roll, dice(1, 20))
		ac_mod = player.get_ac_bonus()
		AC = 10 + ac_mod
		bonus = attack.to_hit
		total = roll + bonus
		if roll == 1:
			hits = False
		elif roll == 20:
			hits = True
		else:
			hits = total >= AC
		if not hits:
			if roll == 1 or total < AC - ac_mod:
				self.g.print_msg(f"The {self.name}'s attack misses you.")
			else:
				self.g.print_msg(f"You evade the {self.name}'s attack.")
		else:
			damage = dice(*attack.dmg)
			if player.has_effect("Resistance"):
				damage = div_rand(damage, 2)
				if random.randint(1, 2) == 1: #Don't tell them every time
					self.g.print_msg("Your resistance blocks some of the damage.")
			if damage < 1:
				damage = 1
			self.g.print_msg(attack.msg.format(self.name) + f" for {damage} damage!", "red")
			player.take_damage(damage)
			
	def do_melee_attack(self):
		for att in self.attacks:
			self.melee_attack_player(att)
			
	def sees_player(self):
		player = self.g.player
		if player.has_effect("Invisible"):
			return False
		return (self.x, self.y) in player.fov
		
	def on_player_attacked(self):
		player = self.g.player
		self.is_aware = True
		self.last_seen = (player.x, player.y)
		
	def can_guess_invis(self):
		#Can we correctly guess the player's position when invisible?
		player = self.g.player
		guessplayer = dice(1, 20) + div_rand(self.WIS - 10, 2) >= dice(1, 20) + div_rand(player.DEX - 10, 2)
		xdist = player.x - self.x
		ydist = player.y - self.y
		dist = abs(xdist) + abs(ydist)
		chance = 2 if dist <= 1 else 6
		guessplayer = guessplayer and random.randint(1, chance	) == 1	
		return guessplayer
		
	def guess_rand_invis(self):
		board = self.g.board
		tries = 100
		while tries > 0:
			dx = random.randint(-2, 2)
			dy = random.randint(-2, 2)
			if (dx, dy) == (0, 0):
				continue
			xp = self.x + dx
			yp = self.y + dy
			if (xp < 0 or xp >= board.cols) or (yp < 0 or yp >= board.cols):
				continue
			if board.blocks_sight(xp, yp) or not board.line_of_sight((self.x, self.y), (xp, yp)):
				tries -= 1
			else:
				self.last_seen = (xp, yp)
				break
				
	def stop_tracking(self):
		self.last_seen = None
		self.track_timer = 0
		self.is_aware = False
		self.dir = None
		
	def actions(self):
		if self.has_effect("Asleep"): #If we're asleep, return early
			self.energy = 0
			return
		board = self.g.board
		player = self.g.player
		confused = self.has_effect("Confused") and random.randint(1, 4) < 4
		guessplayer = False
		if self.is_aware and player.has_effect("Invisible"):
			guessplayer = self.can_guess_invis() #Even if the player is invisible, the monster may still be able to guess their position
		if confused:
			dirs = [(-1, 0), (1, 0), (0, 1), (0, -1)]
			if not self.move(*random.choice(dirs)): #Only try twice
				if not self.move(*random.choice(dirs)):
					self.energy -= div_rand(self.speed, 2) #We bumped into something while confused
			self.energy = min(self.energy, 0)
		elif self.is_aware and (self.sees_player() or guessplayer):
			xdist = player.x - self.x
			ydist = player.y - self.y
			dist = abs(xdist) + abs(ydist)
			self.last_seen = (player.x, player.y)
			self.track_timer = random.randint(25, 65) #How long we remember the player for when out of line of sight
			if dist <= 1:
				self.energy -= self.speed
				self.do_melee_attack()
			elif self.ranged and self.should_use_ranged():
				self.g.print_msg(f"The {self.name} makes a ranged attack at you.")
				for point in board.line_between((self.x, self.y), (player.x, player.y), skipfirst=True, skiplast=True):
					self.g.set_projectile_pos(*point)
					self.g.draw_board()
					time.sleep(0.08)
				self.g.clear_projectile()
				roll = dice(1, 20)
				if player.has_effect("Invisible"): #The player is harder to hit when invisible
					roll = min(roll, dice(1, 20))
				bonus = self.to_hit
				dodge_mod = player.get_ac_bonus()
				AC = 10 + dodge_mod
				total = roll + self.to_hit
				if roll == 1:
					hits = False
				elif roll == 20:
					hits = True
				else:
					hits = total >= AC
				if not hits:
					if roll > 1 and total >= AC - dodge_mod:
						self.g.print_msg("You dodge the projectile.")
					else:
						self.g.print_msg("The projectile misses you.")
				else:
					damage = dice(*self.ranged_dam)
					if player.has_effect("Resistance"):
						damage = div_rand(damage, 2)
						if random.randint(1, 2) == 1: #Don't tell them every time
							self.g.print_msg("Your resistance blocks some of the damage.")
					if damage < 1:
						damage = 1
					self.g.print_msg(f"You are hit for {damage} damage!", "red")
					player.take_damage(damage)
				self.energy -= self.speed
			else:
				dx = 1 if xdist > 0 else (-1 if xdist < 0 else 0)
				dy = 1 if ydist > 0 else (-1 if ydist < 0 else 0)
				axdist = abs(xdist)
				aydist = abs(ydist)
				if axdist > aydist or (axdist == aydist and random.randint(1, 2) == 1):
					maintains = board.line_of_sight((self.x + dx, self.y), (player.x, player.y)) #Choose a direction that doesn't break line of sight
					if not (maintains and self.move(dx, 0)):
						self.move(0, dy)
				else:
					maintains =  board.line_of_sight((self.x, self.y + dy), (player.x, player.y))
					if not (maintains and self.move(0, dy)):
						self.move(dx, 0)
		else:
			if player.has_effect("Invisible") and (self.x, self.y) == self.last_seen:
				self.guess_rand_invis() #Guess a random position if the player is invisible
			if self.last_seen:
				if self.track_timer > 0:
					self.track_timer -= 1
					if player.has_effect("Invisible"):
						check = dice(1, 20) + calc_mod(player.DEX) < 10 + calc_mod(self.WIS)
					else:
						check = True
					self.path_towards(*self.last_seen)
					if (self.x, self.y) == self.last_seen and check:
						#If we reach the target position and still don't see the player, roll a stealth check to continue tracking the player
						if dice(1, 20) + calc_mod(player.DEX) < 10 + calc_mod(self.WIS):
							self.last_seen = (player.x, player.y)
						else:
							self.stop_tracking()
				else:
					self.stop_tracking()
			elif random.randint(1, 6) < 6:
				choose_new = self.dir is None or (random.randint(1, 3) == 1 or not self.move(*self.dir))
				if choose_new:
					if self.dir is None:
						dirs = [(-1, 0), (1, 0), (0, 1), (0, -1)]
						random.shuffle(dirs)
						for d in dirs:
							if self.move(*d):
								self.dir = d
								break
					else:
						if self.dir in [(-1, 0), (1, 0)]:
							dirs = [(0, 1), (0, -1)]
						else:
							dirs = [(-1, 0), (1, 0)]
						random.shuffle(dirs)
						for d in dirs:
							if self.move(*d):
								self.dir = d
								break
						else:
							if not self.move(*self.dir):
								d = (-self.dir[0], -self.dir[1])
								self.move(*d)
								self.dir = d
			

#Balance:
#2x HP and damage from DnD							
class Bat(Monster):
	min_level = 1
	diff = 1
	AC = 12
	WIS = 12
	attacks = [
		Attack((1, 3), 0, "The {0} bites you")
	]	
	
	def __init__(self, g):
		#name, symbol, HP, ranged, ranged_dam
		#ranged == None means there is a chance of it using a ranged attack
		super().__init__(g, "bat", "w", 3, False)

class Lizard(Monster):
	min_level = 1
	diff = 1
	speed = 20
	passive_perc = 9
	WIS = 8
	attacks = [
		Attack((1, 3), 0, "The {0} bites you")
	]
	
	def __init__(self, g):
		super().__init__(g, "lizard", "r", 4, False)
				
class Kobold(Monster):
	diff = 2
	min_level = 3
	AC = 12
	WIS = 7
	to_hit = 4
	passive_perc = 8
	attacks = [
		Attack((2, 4), 4, "The {0} hits you with its dagger")
	]
		
	def __init__(self, g):
		super().__init__(g, "kobold", "K", 10, None, (2, 4))
		
class GiantRat(Monster):
	diff = 2
	min_level = 5
	AC = 12
	to_hit = 4
	passive_perc = 10
	attacks = [
		Attack((2, 4), 4, "The {0} bites you")
	]
	
	def __init__(self, g):
		super().__init__(g, "giant rat", "R", 14, False)

class Skeleton(Monster):
	diff = 3
	min_level = 7
	AC = 12
	WIS = 8
	to_hit = 4
	passive_perc = 9
	attacks = [
		Attack((2, 6), 4, "The {0} hits you with its shortsword")
	]
		
	def __init__(self, g):
		super().__init__(g, "skeleton", "F", 26, None, (2, 6))
		

class GiantBat(Monster):
	diff = 3
	speed = 60
	min_level = 8
	AC = 13
	WIS = 12
	to_hit = 4
	attacks = [
		Attack((2, 6), 4, "The {0} bites you")
	]

	def __init__(self, g):
		super().__init__(g, "giant bat", "W", 26, False)

class GiantLizard(Monster):
	diff = 3
	min_level = 9
	AC = 12
	to_hit = 4
	passive_perc = 10
	attacks = [
		Attack((2, 8), 4, "The {0} bites you")
	]
	
	def __init__(self, g):
		super().__init__(g, "giant lizard", "L", 38, False)

class GiantGoat(Monster):
	diff = 4
	speed = 40
	min_level = 12
	AC = 11
	WIS = 12
	to_hit = 5
	attacks = [
		Attack((4, 4), 4, "The {0} rams you")
	]
		
	def __init__(self, g):
		super().__init__(g, "giant goat", "G", 38, False)

class BlackBear(Monster):
	diff = 4
	speed = 40
	min_level = 12
	AC = 11
	WIS = 2
	to_hit = 3
	passive_perc = 13
	attacks = [
		Attack((2, 6), 3, "The {0} bites you"),
		Attack((4, 4), 3, "The {0} claws you")
	]
		
	def __init__(self, g):
		super().__init__(g, "black bear", "B", 38, False)

class BrownBear(Monster):
	diff = 5
	speed = 40
	min_level = 15
	AC = 11
	WIS = 12
	to_hit = 3
	passive_perc = 13
	attacks = [
		Attack((2, 8), 3, "The {0} bites you"),
		Attack((4, 6), 3, "The {0} claws you")
	]
		
	def __init__(self, g):
		super().__init__(g, "brown bear", "&", 68, False)

class GiantEagle(Monster):
	AC = 13
	WIS = 12
	diff = 5
	min_level = 16
	to_hit = 5
	passive_perc = 14
	attacks = [
		Attack((2, 6), 5, "The {0} attacks you with its beak"),
		Attack((4, 6), 5, "The {0} attacks you with its talons")
	]
		
	def __init__(self, g):
		super().__init__(g, "giant eagle", "E", 52, False)
						
g = Game()
try:
	g.print_msg("Press \"?\" if you want to view the controls.")
	g.generate_level()
	while not g.player.dead:
		refresh = False
		lastenergy = g.player.energy
		if g.player.resting:
			time.sleep(0.005)
			g.player.energy = 0
			if g.player.HP >= g.player.MAX_HP:
				g.print_msg("HP restored.", "green")
				g.player.resting = False
				g.player.energy = g.player.get_speed()
				refresh = True
		else:
			curses.flushinp()
			char = chr(g.screen.getch())
			if char == "w":
				g.player.move(0, -1)
			elif char == "s":
				g.player.move(0, 1)
			elif char == "a":
				g.player.move(-1, 0)
			elif char == "d":
				g.player.move(1, 0)
			elif char == "q": #Scroll up
				g.msg_cursor -= 1
				if g.msg_cursor < 0:
					g.msg_cursor = 0
				refresh = True
			elif char == "z": #Scroll down
				g.msg_cursor += 1
				if g.msg_cursor > (limit := max(0, len(g.msg_list) - g.get_max_lines())):
					g.msg_cursor = limit
				refresh = True
			elif char == "f": #View info of monster types in view
				fov_mons = list(g.player.monsters_in_fov())
				refresh = True
				if not fov_mons:
					g.print_msg("You don't see any monsters right now")
				else:
					fov_mons.sort(key=lambda m: m.name)
					fov_mons.sort(key=lambda m: m.diff)
					dup = set()
					rem_dup = []
					for m in fov_mons:
						if m.name not in dup:
							rem_dup.append(m)
							dup.add(m.name)
					fov_mons = rem_dup[:]
					del rem_dup
					ac_bonus = g.player.get_ac_bonus(avg=True)
					str_mod = calc_mod(g.player.STR, avg=True)
					for m in fov_mons:
						hit_prob = to_hit_prob(m.AC, str_mod)
						hit_adv = to_hit_prob(m.AC, str_mod, adv=True) #Probability with advantage
						#TODO: Remove to_hit from the Attack object as they seem to be the same for monsters
						#The to_hit can just be linked to the monster value instead
						be_hit = to_hit_prob(10 + ac_bonus, m.to_hit)
						be_hit_disadv = to_hit_prob(10 + ac_bonus, m.to_hit, disadv=True)
						string = f"{m.symbol} - {m.name} "
						string += f"| To hit: {display_prob(hit_prob*100)} ({display_prob(hit_adv*100)} w/adv.)"
						string += f" | {display_prob(be_hit*100)} to hit you ({display_prob(be_hit_disadv*100)} w/disadv.)"
						string += " | Attacks: "
						for i in range(len(m.attacks)):
							att = m.attacks[i] 
							x, y = att.dmg
							string += f"{x}d{y}"
							if i < len(m.attacks) - 1:
								string += ", "
						g.print_msg(string)
			elif char == "u": #Use an item
				if g.player.inventory:
					g.print_msg("Which item would you like to use?")
					inv = g.player.inventory[:]
					d = {}
					for item in inv:
						name = item.name
						if name not in d:
							d[name] = 0
						d[name] += 1
					strings = []
					for name in sorted(d.keys()):
						if d[name] == 1:
							strings.append(name)
						else:
							strings.append(name + f" ({d[name]})")
					g.print_msg("You have: " + ", ".join(strings))
					name = g.input()
					item = next((it for it in g.player.inventory if it.name == name), None)
					if item and item.use(g.player):
						g.player.inventory.remove(item)
						g.player.energy -= g.player.get_speed()
					refresh = True
				else:
					g.print_msg("You don't have anything to use.")
					refresh = True
			elif char == "r" and g.player.HP < g.player.MAX_HP: #Rest and wait for HP to recover
				g.print_msg("You begin resting.")
				g.player.resting = True
			elif char == "p": #Pick up item
				tile = g.board.get(g.player.x, g.player.y)
				if tile.items:
					item = tile.items.pop()
					g.player.inventory.append(item)
					g.print_msg(f"You pick up a {item.name}.")
					g.player.energy -= g.player.get_speed()
				else:
					g.print_msg("There's nothing to pick up.")
					refresh = True
			elif char == " ": #Go down to next level
				if g.board.get(g.player.x, g.player.y).stair:
					time.sleep(0.3)
					g.generate_level()
					g.level += 1
					g.print_msg("You descend deeper into the dungeon.")
				else:
					g.print_msg("You can't go down here.")
				refresh = True
			elif char == "?":
				g.help_menu()
			elif char == ".": #Wait a turn
				g.player.energy = 0
			elif char == "j": #View descriptions of items on this tile
				items = g.board.get(g.player.x, g.player.y).items
				for item in items:
					g.print_msg(f"{item.name} - {item.description}")
				refresh = True
		moved = g.player.energy < lastenergy
		if moved:
			g.do_turn()
			if not g.player.resting or g.player.ticks % 10 == 0:
				g.draw_board()
		elif refresh:
			g.draw_board()
	g.input("Press enter to continue...")
	g.game_over()
except Exception as e:
	curses.nocbreak()
	curses.echo()
	curses.endwin()
	import os, traceback
	os.system("clear")
	print("An error has occured:")
	print()
	msg = traceback.format_exception(type(e), e, e.__traceback__)
	msg = "".join(msg)
	print(msg)
	print()
	filename = "roguelike_error.log"
	f = open(filename, "w")
	try:
		f.write(msg)
		print(f"The error message has been written to {filename}")
	except:
		pass
except KeyboardInterrupt:
	curses.nocbreak()
	curses.echo()
	curses.endwin()
	import os
	os.system("clear")
	raise
else:
	curses.nocbreak()
	curses.echo()