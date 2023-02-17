import random, curses, textwrap
from os import get_terminal_size
from itertools import islice
from collections import deque

from utils import *
from board import Board
from player import Player
from effect import Effect
from monster import Monster
from items import *


class Game:
		
	def __init__(self):
		self.screen = curses.initscr()
		curses.start_color()
		
		curses.init_pair(1, curses.COLOR_RED, 0)
		curses.init_pair(2, curses.COLOR_GREEN, 0)
		curses.init_pair(3, curses.COLOR_YELLOW, 0)
		curses.init_pair(4, curses.COLOR_BLUE, 0)
		curses.init_pair(5, curses.COLOR_MAGENTA, 0)
		
		self.screen.clear()
		curses.noecho()
		self.board = Board(self, 40, 16)
		self.player = Player(self)
		self.monsters = []
		self.msg_list = deque(maxlen=50)
		self.msg_cursor = 0
		self.blast = set()
		self.projectile = None
		self.select = None
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
		add_text("Q - quit the game")
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
		add_text(f"Your final stats were:")
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
		
	def spawn_item(self, item, pos):
		self.board.get(*pos).items.append(item)
		
	def input(self, message=None):
		if message:
			self.print_msg(message)
		self.draw_board()
		curses.echo()
		string = self.screen.getstr()
		curses.noecho()
		self.draw_board()
		return string.decode()
		
	def yes_no(self, message):
		while (choice := self.input(message + " (Y/N)").lower()) not in ["y", "n"]:
			self.print_msg("Please enter \"Y\" or \"N\"")
		return choice == "y"
		
	def select_monster_target(self, cond=None, error="None of the monsters are eligible targets."):
		monsters = list(self.player.monsters_in_fov())
		if not monsters:
			self.print_msg("You don't see any monsters to target.")
			return None
		if cond:
			monsters = list(filter(cond, monsters))
			if not monsters:
				self.print_msg(error)
				return None
		self.print_msg("Target which monster?")
		self.print_msg("Use the a and d keys to select")
		monsters.sort(key=lambda m: m.y)
		monsters.sort(key=lambda m: m.x)
		index = random.randrange(len(monsters))
		last = -1
		while True:
			self.select = monsters[index]
			if last != index:
				self.draw_board()
				last = index
			curses.flushinp()
			num = self.screen.getch()
			char = chr(num)
			if char == "a":
				index -= 1
				if index < 0:
					index += len(monsters)
			elif char == "d":
				index += 1
				if index >= len(monsters):
					index -= len(monsters)
			if num == 10:
				break
		self.select = None
		return monsters[index]
		
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
			pool = []
			for t in monsters:
				if self.level > int((t.min_level - 1)*random.uniform(1, 1.7)):
					pool.append(t)
			assert len(pool) > 0
			typ = random.choice(pool)	
			m = typ(self)
			if m.place_randomly():
				if one_in(2):
					fov = self.player.fov
					los_tries = 100
					while los_tries > 0:
						if (m.x, m.y) not in fov:
							break
						m.place_randomly()
						los_tries -= 1
				self.monsters.append(m)
		
		def place_item(typ):
			for j in range(250):
				x = random.randint(1, self.board.cols - 2)
				y = random.randint(1, self.board.rows - 2)
				if self.board.is_passable(x, y):
					tile = self.board.get(x, y)
					if not tile.items:
						tile.items.append(typ())
						break
						
		if not one_in(8):	
			types = [
				(HealthPotion, 55),
				(ResistPotion, 20),
				(SpeedPotion, 20),
				(InvisibilityPotion, 12),
				(RejuvPotion, 3)
			]
			for _ in range(4):
				if x_in_y(45, 100):
					typ = rand_weighted(*types)
					place_item(typ)	
				elif x_in_y(60, 100):
					break
						
			if self.level > dice(1, 6) and x_in_y(3, 8):
				typ = rand_weighted(
					(MagicMissile, 10),
					(PolymorphWand, 5),
					(WandOfFear, 3),
					(LightningWand, 2)
				)
				place_item(typ)
			
			if x_in_y(3, 8):
				typ = rand_weighted(
					(StunScroll, 1),
					(TeleportScroll, 2),
					(SleepScroll, 1),
					(ConfusionScroll, 2)
				)
				place_item(typ)
				
			if not one_in(3):
				types = [
					(Club, 60),
					(Dagger, 30),
					(Greatclub, 30),
					(Handaxe, 12),
					(Javelin, 12),
					(Mace, 12),
					(Battleaxe, 6),
					(Glaive, 3),
					(Greataxe, 2),
				]
				for _ in range(random.randint(2, 3)):
					if not one_in(3):
						place_item(rand_weighted(*types))
				
			if self.level > 1 and x_in_y(min(55 + self.level, 80), 100):
				types = [LeatherArmor]
				if self.level > 2:
					types.append(HideArmor)
				if self.level > 5:
					types.append(ChainShirt)
				if self.level > 8:
					types.append(ScaleMail)
				if self.level > 10:
					types.append(HalfPlate)
				num = 1
				if self.level > random.randint(1, 3) and one_in(3):
					num += 1
					if self.level > random.randint(1, 6) and one_in(3):
						num += 1
				for _ in range(num):
					place_item(random.choice(types))
			
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
		screen.addstr(0, 0, f"HP {p.HP}/{p.get_max_hp()} | DG. LV {self.level} | XP {p.exp}/{p.max_exp()} ({p.level})")
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
					if isinstance(item, (Scroll, Armor)):
						color = curses.color_pair(4) | curses.A_BOLD
					elif isinstance(item, Wand):
						color = curses.color_pair(5) | curses.A_BOLD
					elif isinstance(item, Weapon):
						color = curses.color_pair(5) | curses.A_REVERSE
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
		monpos = set()
		for m in self.monsters:
			x, y = m.x, m.y
			if (x, y) in fov:
				monpos.add((x, y))
				color = curses.color_pair(3) if m.ranged else 0
				if m.has_effect("Confused"):
					color = curses.color_pair(4)
				elif m.has_effect("Stunned"):
					color = curses.color_pair(5)
				elif not m.is_aware:
					if m.has_effect("Asleep"):
						color = curses.color_pair(4)
					color |= curses.A_REVERSE
				if m is self.select or (m.x, m.y) in self.blast:
					color = curses.color_pair(2)
					color |= curses.A_REVERSE 
				try:
					screen.addstr(y+offset, x, m.symbol, color)
				except curses.error:
					pass
		for x, y in (self.blast - monpos):
			try:
				screen.addstr(y+offset, x, " ", curses.color_pair(2) | curses.A_REVERSE)
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
		weapon = self.player.weapon
		if weapon:
			X, Y = weapon.dmg
			w = f"{weapon.name} ({X}d{Y})"
		else:
			w = "unarmed (1d2)"
		screen.addstr(2, wd - len(w), w)
		armor = self.player.armor
		if armor:
			ar_str = f"{armor.name} ({armor.protect})"
			screen.addstr(3, wd - len(ar_str), ar_str)
		detect = self.player.detectability()
		if detect is not None:
			stealth = round(1/max(detect, 0.01) - 1, 1)
			det_str = f"{stealth} stealth"
			screen.addstr(4, wd - len(det_str), det_str)
		
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
			if one_in(10): #In case anything goes wrong, refresh the monster collision cache every so often
				self.refresh_cache()
			self.player.do_turn()
			order = self.monsters[:]
			random.shuffle(order)
			order.sort(key=lambda m: m.get_speed(), reverse=True)
			self.player.energy += self.player.get_speed()		
			for m in order:
				if m.HP > 0:
					m.do_turn()
				else:
					self.monsters.remove(m)
				if self.player.dead:
					return
					
