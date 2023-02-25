try:
	import curses
except:	
	print("The builtin curses module is not supported on Windows.")
	print("However, you can install the windows-curses module in order to play on Windows.")
	while True:
		print("Would you like to install windows-curses? (Y/N)")
		choice = input(">> ")
		if choice:
			c = choice[0].lower()
			if c == "y":
				print("Beginning installation...")
				import subprocess
				code = subprocess.call(["pip", "install", "windows-curses"])
				if code:
					print("Failed to install windows-curses.")
					exit(code)
				break
			elif c == "n":
				exit()
			else:
				print("Please enter Y or N")
	import curses
	os.system("cls" if os.name == "nt" else "clear")
	
import random, time
import math
from collections import deque
from os import get_terminal_size

from utils import *
from board import *	
from gameobj import *					
from entity import *		
from items import *
from monster import *

if __name__ == "__main__":		
	g = Game()
	try:
		g.print_msg("Press \"?\" if you want to view the controls.")
		if g.has_saved_game():
			g.maybe_load_game()	
		if not g.has_saved_game(): #Either it failed to load or the player decided to start a new game
			g.generate_level()
			item = SummonScroll
			for _ in range(100):
				g.player.inventory.append(item())
		for w in dup_warnings:
			g.print_msg(f"WARNING: {w}", "yellow")	
		g.draw_board()
		g.refresh_cache()
		while not g.player.dead:
			refresh = False
			lastenergy = g.player.energy
			if g.player.resting:
				g.screen.nodelay(True)
				char = g.screen.getch()
				done = False
				if char != -1 and chr(char) == "r":
					g.screen.nodelay(False)
					if g.yes_no("Really cancel your rest?"):
						done = True
						g.print_msg("You stop resting.")
					else:
						g.print_msg("You continue resting.")
						g.screen.nodelay(True)
				time.sleep(0.005)
				g.player.energy = 0
				if not done and g.player.HP >= g.player.get_max_hp():
					g.print_msg("HP restored.", "green")
					done = True
				if done:
					g.screen.nodelay(False)
					g.player.resting = False
					g.player.energy = random.randint(1, g.player.get_speed())
					refresh = True
			elif g.player.activity:
				time.sleep(0.01)
				g.player.energy = 0
				g.player.activity.time -= 1
				if g.player.activity.time <= 0:
					g.player.activity.on_finished(g.player)
					g.player.activity = None
					refresh = True
					g.player.energy = random.randint(1, g.player.get_speed())
			else:
				g.screen.nodelay(False)
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
						mod = g.player.attack_mod(avg=True)
						str_mod = calc_mod(g.player.STR, avg=True)
						AC = 10 + ac_bonus - 2 * len(g.player.grappled_by)
						for m in fov_mons:
							hit_prob = to_hit_prob(m.AC, mod)
							hit_adv = to_hit_prob(m.AC, mod, adv=True) #Probability with advantage
							be_hit = to_hit_prob(AC, m.to_hit)
							be_hit_disadv = to_hit_prob(AC, m.to_hit, disadv=True)
							string = f"{m.symbol} - {m.name} "
							string += f"| To hit: {display_prob(hit_prob*100)} ({display_prob(hit_adv*100)} w/adv.)"
							string += f" | {display_prob(be_hit*100)} to hit you ({display_prob(be_hit_disadv*100)} w/disadv.)"
							string += " | Attacks: "
							for i in range(len(m.attacks)):
								att = m.attacks[i]
								if isinstance(att, list):
									d = []
									for a in att:
										x, y = a.dmg
										d.append(f"{x}d{y}")
										if i < len(att) - 1:
											d.append(", ")
									d = "".join(d)
									string += f"({d})"
								else:
									x, y = att.dmg
									string += f"{x}d{y}"
								if i < len(m.attacks) - 1:
									string += ", "
							if m.armor > 0:
								string += f" | Armor: {m.armor}"
							g.print_msg(string)
				elif char == "u": #Use an item
					if g.player.inventory:
						g.print_msg("Which item would you like to use?")
						inv = g.player.inventory[:]
						d = {}
						for item in inv:
							name = item.name
							if isinstance(item, Wand):
								name += f" - {item.charges} charges"
							if name not in d:
								d[name] = [0, item]
							d[name][0] += 1
						strings = []
						choices = []
						for i, name in enumerate(sorted(d.keys())):
							n = name
							num, item = d[name]
							if num > 1:
								n += f" ({num})"
							strings.append(f"{i+1}. {n}")
							choices.append(item)
						g.print_msg("Enter a number")
						g.print_msg("You have: " + ", ".join(strings))
						num = g.input()
						try:
							num = int(num)
						except ValueError:
							g.print_msg("You didn't enter a number.")
						else:
							if num <= 0 or num > len(strings):
								g.print_msg(f"Invalid number. Must be between 1 and {len(strings)}")
							else:
								item = choices[num - 1]
								result = item.use(g.player)
								if result is not False: #False to not use time up a turn or the item
									if result is not None: #None uses a turn without removing the item
										g.player.inventory.remove(item)
									g.player.energy -= g.player.get_speed()
						refresh = True
					else:
						g.print_msg("You don't have anything to use.")
						refresh = True
				elif char == "r" and g.player.HP < g.player.MAX_HP: #Rest and wait for HP to recover 
					aware_count = 0
					for m in g.player.monsters_in_fov():
						if m.is_aware:
							aware_count += 1
					if aware_count == 0:
						g.print_msg("You begin resting.")
						g.player.resting = True
					else:
						num_msg = "there are monsters" if aware_count > 1 else "there's a monster"
						g.print_msg(f"You can't rest when {num_msg} nearby!", "yellow")
					refresh = True
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
						was_any_allies = any(m.summon_timer is not None for m in g.monsters)
						time.sleep(0.3)
						g.generate_level()
						g.level += 1
						if was_any_allies:
							g.print_msg("You descend deeper into the dungeon, leaving your summoned allies behind.")
						else:
							g.print_msg("You descend deeper into the dungeon.")
						
						for m in g.player.monsters_in_fov():
							if x_in_y(3, g.level):
								continue
							if dice(1, 20) + calc_mod(g.player.DEX) - 4 < m.passive_perc:
								m.is_aware = True
					else:
						g.print_msg("You can't go down here.")
					refresh = True
				elif char == "?":
					g.help_menu()
				elif char == ".": #Wait a turn
					g.player.energy = 0
				elif char == "Q": #Quit
					if g.yes_no("Are you sure you want to quit the game?"):
						curses.nocbreak()
						curses.echo()
						exit()
				elif char == "j": #View descriptions of items on this tile
					items = g.board.get(g.player.x, g.player.y).items
					for item in items:
						g.print_msg(f"{item.name} - {item.description}")
					refresh = True
				elif char == "t":
					g.player.throw_item()
					refresh = True
			moved = g.player.energy < lastenergy
			if moved:
				g.do_turn()
				busy = g.player.resting or g.player.activity
				if not busy or g.player.ticks % 10 == 0:
					g.draw_board()
				if not busy or g.player.ticks % 35 == 0:
					g.save_game()
			elif refresh:
				g.draw_board()
		g.delete_saved_game()
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
		os.system("cls" if os.name == "nt" else "clear")
		raise
	else:
		curses.nocbreak()
		curses.echo()