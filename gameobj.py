import random, curses, textwrap
from os import get_terminal_size, path
from itertools import islice
from collections import deque

from utils import *
from board import Board
from player import Player
from effect import Effect
from monster import Monster
from items import *

import pickle

class GameTextMenu:
	
	def __init__(self, g):
		self.screen = g.screen
		self.g = g
		size = get_terminal_size()
		self.termwidth = size.columns
		self.msg = []
		
	def add_text(self, txt):
		txt = str(txt)
		self.msg.extend(textwrap.wrap(txt, self.termwidth))
		
	def add_line(self):
		self.msg.append("")
		
	def clear_msg(self):
		self.msg.clear()
	
	def display(self):
		self.screen.clear()
		for i in range(len(self.msg)):
			self.screen.addstr(i, 0, self.msg[i])
		self.screen.refresh()
			
	def close(self):
		self.g.draw_board()
		
	def getch(self):
		return self.screen.getch()
		
	def getchar(self):
		return chr(self.getch())
		
	def wait_for_enter(self):
		while self.getch() != 10: pass

class Game:
	_INST = None
	
	def __new__(cls):
		if cls._INST:
			return cls._INST
		obj = object.__new__(cls)
		cls._INST = obj
		return obj
	
	def __init__(self):
		self.screen = curses.initscr()
		curses.start_color()
		curses.init_pair(1, curses.COLOR_RED, 0)
		curses.init_pair(2, curses.COLOR_GREEN, 0)
		curses.init_pair(3, curses.COLOR_YELLOW, 0)
		curses.init_pair(4, curses.COLOR_BLUE, 0)
		curses.init_pair(5, curses.COLOR_MAGENTA, 0)
		curses.init_pair(6, curses.COLOR_CYAN, 0)
		
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
		self.revealed = []
		types = Effect.__subclasses__()
		self.effect_types = {t.name:t for t in types}
		self.mon_types = Monster.__subclasses__()
		
	def __getstate__(self):
		d = self.__dict__.copy()
		del d["screen"]
		return d
	
	def __setstate__(self, state):
		self.__dict__.update(state)
		self.screen = curses.initscr()
		
	def load_game(self):
		try:
			obj = pickle.load(open("save.pickle", "rb"))
			self.__dict__.update(obj.__dict__)
		except:
			self.print_msg("Unable to load saved game.", "yellow")
			self.delete_saved_game()
			
	def save_game(self):
		pickle.dump(self, open("save.pickle", "wb"))
		
	def has_saved_game(self):
		return path.exists("save.pickle")
	
	def delete_saved_game(self):
		if self.has_saved_game():
			import os
			os.remove("save.pickle")
	
	def help_menu(self):
		menu = GameTextMenu(self)
		menu.add_text("Use the wasd keys to move")
		menu.add_text("Use the q and z keys to scroll the message log")
		menu.add_text("f - view info about monsters currently in view")
		menu.add_text("r - rest until HP is recovered")
		menu.add_text("p - pick up item")
		menu.add_text("i - inventory menu")
		menu.add_text("space - go down to next level (when standing on a \">\" symbol)")
		menu.add_text("? - brings up this menu again")
		menu.add_text(". - wait a turn")
		menu.add_text("t - throw a throwable item")
		menu.add_text("+ - view equipped rings (and bonuses from them)")
		menu.add_text("Q - quit the game")
		menu.add_line()
		menu.add_text("Press enter to continue")
		menu.display()
		menu.wait_for_enter()
		menu.close()
	
	def maybe_load_game(self):
		if not self.has_saved_game():
			return
		menu = GameTextMenu(self)	
		while True:
			menu.clear_msg()
		
			menu.add_text("Continue Saved Game")
			menu.add_line()
			menu.add_text("You have a saved game.")
			menu.add_line()
			menu.add_text("Press 1 to load saved game.")
			menu.add_text("Press 2 to start a new game.")
			menu.display()
			while (user := chr(menu.getch())) not in ["1", "2"]: pass
			if user == "1":
				self.load_game()
				break
			else:
				menu.clear_msg()
				menu.add_text("Really start a new game? All progress will be lost!")
				menu.add_line()
				menu.add_text("Enter Y or N")
				menu.display()
				while (newgame := chr(menu.getch()).upper()) not in ["Y", "N"]: pass
				if newgame == "Y":
					self.delete_saved_game()
					break
				
		menu.close()
		
	def game_over(self):
		menu = GameTextMenu(self)				
		p = self.player
		menu.add_text("GAME OVER")
		menu.add_line()
		menu.add_text(f"You reached Dungeon Level {self.level}")
		menu.add_text(f"You attained XP level {p.level}")
		menu.add_line()
		menu.add_text(f"Your final stats were:")
		menu.add_text(f"STR {p.STR}, DEX {p.DEX}")
		menu.add_line()
		menu.add_text("Press enter to quit")
		menu.display()
		menu.wait_for_enter()
			
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
			
	def add_monster_at(self, m, pos):
		if m.place_randomly():
			self.monsters.append(m)
			
	def place_monster(self, typ):
		m = typ(self)
		if m.place_randomly():
			self.monsters.append(m)
			return m
		return None
	
	def generate_level(self):
		self.monsters.clear()
		self.board.generate()
		self.player.rand_place()
		self.player.fov = self.player.calc_fov()
		num = random.randint(3, 4) + random.randint(0, int(1.4*(self.level - 1)**0.65))
		monsters = self.mon_types
		pool = []
		for t in monsters:
			lev = self.level
			if lev >= t.min_level:
				pool.append(t)
		assert len(pool) > 0
		for _ in range(num):
			typ = random.choice(pool)	
			m = typ(self)
			fuzz = max(1, m.MAX_HP//10)
			delta = random.randint(0, fuzz) - random.randint(0, fuzz)
			new_HP = max(1, m.MAX_HP + delta)
			m.HP = m.MAX_HP = new_HP
			if m.place_randomly():
				if one_in(2) and x_in_y(8, self.level):
					los_tries = 100
					while los_tries > 0:
						if not self.player.sees((m.x, m.y)):
							break
						m.place_randomly()
						los_tries -= 1
				self.monsters.append(m)
		
		def place_item(typ):
			for j in range(600):
				x = random.randint(1, self.board.cols - 2)
				y = random.randint(1, self.board.rows - 2)
				if self.board.is_passable(x, y):
					tile = self.board.get(x, y)
					if not tile.items:
						tile.items.append(item := typ())
						return item
			return None
						
		if not one_in(8):	
			types = [
				(HealthPotion, 55),
				(ResistPotion, 20),
				(SpeedPotion, 20),
				(InvisibilityPotion, 12),
				(RejuvPotion, 3),
				(ClairPotion, 9)
			]
			for _ in range(4):
				if x_in_y(45, 100):
					typ = rand_weighted(*types)
					place_item(typ)	
				elif x_in_y(60, 100):
					if one_in(2):
						place_item(HealthPotion)
					break
					
			if one_in(5):
				typ = random.choice([StrengthRing, ProtectionRing, DexterityRing])
				place_item(typ)
				
			if self.level > dice(1, 6) and x_in_y(3, 8):
				typ = rand_weighted(
					(MagicMissile, 10),
					(PolymorphWand, 5),
					(WandOfFear, 3),
					(LightningWand, 2)
				)
				place_item(typ)
			
			if x_in_y(2, 5):
				typ = rand_weighted(
					(StunScroll, 2),
					(TeleportScroll, 3),
					(SleepScroll, 2),
					(ConfusionScroll, 3),
					(SummonScroll, 2),
					(EnchantScroll, 4)
				)
				place_item(typ)
			elif one_in(3):
				place_item(EnchantScroll)
				
			types = [
				(Club, 65),
				(Dagger, 35),
				(Greatclub, 35),
				(Handaxe, 17),
				(Javelin, 17),
				(Mace, 17),
				(Battleaxe, 11),
				(Shortsword, 11),
				(Longsword, 9),
				(Morningstar, 9),
				(Glaive, 8),
				(Greataxe, 7),
			]
			types = [t for t in types if t[1] >= int(65/self.level)]
			num = binomial(random.randint(2, 3), 50)
			for _ in range(num):
				if (weapon := place_item(rand_weighted(*types))):
					if one_in(20):
						for _ in range(3):
							weapon.add_enchant()
							if not one_in(3):
								break
				
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
				if self.level > 13:
					types.append(SplintArmor)
				if self.level > 15:
					types.append(PlateArmor)
				num = 1
				if self.level > random.randint(1, 3) and one_in(3):
					num += 1
					if self.level > random.randint(1, 6) and one_in(3):
						num += 1
				for _ in range(num):
					place_item(random.choice(types))
		
		self.revealed.clear()
		self.draw_board()
		self.refresh_cache()
	
	def monster_at(self, x, y, include_player=False):
		if (x, y) == (self.player.x, self.player.y):
			return include_player
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
		if self.player.sees(pos, clairv=True):
			self.print_msg(msg, color=color)
			
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
		hp_str = f"HP {p.HP}/{p.get_max_hp()}"
		c = 0
		if p.HP <= p.get_max_hp()//8:
			c = curses.color_pair(1) | curses.A_BOLD
		elif p.HP <= p.get_max_hp()//4:
			c = curses.color_pair(3) 
		width = get_terminal_size().columns
		screen.addstr(0, 0, hp_str, c)
		dr = ""
		if p.hp_drain > 0:
			extent = p.hp_drain//10+1
			dr = f" (Drain {extent})" 
		screen.addstr(0, len(hp_str), f"{dr} | DG. LV {self.level} | XP {p.exp}/{p.max_exp()} ({p.level})")
		wd = min(width, 60)
		str_string = f"STR {p.STR}"
		screen.addstr(0, wd - len(str_string), str_string, self._stat_mod_color(p.mod_str))
		dex_string = f"DEX {p.DEX}"
		screen.addstr(1, wd - len(dex_string), dex_string, self._stat_mod_color(p.mod_dex))
		dmgdice = p.weapon.dmg
		X = dmgdice.num
		Y = dmgdice.sides
		w = f"{p.weapon.name} ({X}d{Y})"
		screen.addstr(2, wd - len(w), w)
		armor = self.player.armor
		if armor:
			ar_str = f"{armor.name} ({armor.protect})"
			screen.addstr(3, wd - len(ar_str), ar_str)
		detect = p.detectability()
		if detect is not None:
			stealth = round(1/max(detect, 0.01) - 1, 1)
			det_str = f"{stealth} stealth"
			screen.addstr(4, wd - len(det_str), det_str)
		
		
		fov = self.player.fov.copy()
		if self.player.has_effect("Clairvoyance"):
			for point in self.board.get_in_circle((self.player.x, self.player.y), 8):
				x, y = point
				neighbors = [(x+1, y), (x-1, y), (x, y+1), (x, y-1), (x+1, y+1), (x+1, y-1), (x-1, y+1), (x-1, y-1)]
				surrounded = True
				for xp, yp in neighbors:
					if not self.board.in_bounds(xp, yp):
						continue
					if not board.blocks_sight(xp, yp):
						surrounded = False
						break
				if not surrounded:
					fov.add(point)
					
		for point in fov:
			tile = board.get(*point)
			if not tile.revealed:
				tile.revealed = True
				self.revealed.append(point)
		offset = 1
		marked = set()
		for col, row in self.revealed:
			tile = board.get(col, row)
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
			if (col, row) in self.blast:
				color = curses.color_pair(2)
				color |= curses.A_REVERSE
				marked.add((col, row))
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
				elif m.is_friendly():
					color = curses.color_pair(6)
				if m is self.select or (m.x, m.y) in self.blast:
					color = curses.color_pair(2)
					color |= curses.A_REVERSE
				try:
					screen.addstr(y+offset, x, m.symbol, color)
				except curses.error:
					pass
		for x, y in (self.blast - monpos - marked):
			if not self.board.in_bounds(x, y):
				continue
			try:
				screen.addstr(y+offset, x, " ", curses.color_pair(2) | curses.A_REVERSE)
			except curses.error:
				pass
		
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
		
		try:
			screen.move(board.rows + offset, 0)
		except curses.error:
			pass
		screen.refresh()
		
	def _stat_mod_color(self, mod):
		if mod > 0:
			return curses.color_pair(2)
		if mod < 0:
			return curses.color_pair(1)
		return 0
		
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
					self.remove_monster(m)
				if self.player.dead:
					return