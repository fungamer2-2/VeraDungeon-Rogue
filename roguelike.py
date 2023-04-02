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
	profiler = cProfile.Profile()
	profiler.enable()
	g = Game()
	try:
		g.print_msg("Welcome to VeraDugeon Rogue v0.5")
		g.print_msg("Press \"?\" if you want to view the controls.")
		if g.has_saved_game():
			g.maybe_load_game()	
		if not g.has_saved_game(): #Either it failed to load or the player decided to start a new game
			g.generate_level()
		for w in dup_warnings:
			g.print_msg(f"WARNING: {w}", "yellow")	
		g.draw_board()
		g.refresh_cache()
		player = g.player
		g.player.recalc_passives()
		while not player.dead:
			refresh = False
			lastenergy = player.energy
			if player.resting:
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
				player.energy = 0
				if not done and player.HP >= player.get_max_hp():
					g.print_msg("HP restored.", "green")
					done = True
				if done:
					g.screen.nodelay(False)
					g.player.resting = False
					player.energy = random.randint(1, player.get_speed())
					refresh = True
					g.save_game()
			elif g.player.activity:
				time.sleep(0.01)
				player.energy = 0
				player.activity.time -= 1
				if player.activity.time <= 0:
					player.activity.on_finished(player)
					player.activity = None
					refresh = True
					player.energy = random.randint(1, player.get_speed())
					g.save_game()
			else:
				g.screen.nodelay(False)
				curses.flushinp()
				char = chr(g.screen.getch())
				if char == "w":
					player.move(0, -1)
				elif char == "s":
					player.move(0, 1)
				elif char == "a":
					player.move(-1, 0)
				elif char == "d":
					player.move(1, 0)
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
					fov_mons = list(player.monsters_in_fov(clairvoyance=True))
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
						ac_bonus = player.get_ac_bonus(avg=True)
						mod = player.attack_mod(avg=True)
						str_mod = calc_mod(g.player.STR, avg=True)
						AC = 10 + ac_bonus
						mon_AC = m.get_ac(avg=True)
						for m in fov_mons:
							hit_prob = to_hit_prob(mon_AC, mod)
							hit_adv = to_hit_prob(mon_AC, mod, adv=True) #Probability with advantage
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
				elif char == "u": #Use an item - migrated to Inventory menu
					g.print_msg("The \"Use\" keybind has been migrated to the \"Inventory\" keybind. Use the \"i\" key instead to open the inventory.")
					refresh = True
				elif char == "i": #Inventory menu
					if player.inventory:
						player.inventory_menu()
					else:
						g.print_msg("You don't have anything in your inventory.")
						refresh = True
				elif char == "r" and player.HP < player.MAX_HP: #Rest and wait for HP to recover 
					aware_count = 0
					for m in player.monsters_in_fov():
						if m.is_aware:
							aware_count += 1
					if aware_count == 0:
						g.print_msg("You begin resting.")
						player.resting = True
					else:
						num_msg = "there are monsters" if aware_count > 1 else "there's a monster"
						g.print_msg(f"You can't rest when {num_msg} nearby!", "yellow")
					refresh = True
				elif char == "p": #Pick up item
					tile = g.board.get(player.x, player.y)
					if tile.items:
						item = tile.items.pop()
						g.player.add_item(item)
						g.print_msg(f"You pick up a {item.name}.")
						g.player.energy -= g.player.get_speed()
					else:
						g.print_msg("There's nothing to pick up.")
						refresh = True
				elif char == " ": #Go down to next level
					if g.board.get(player.x, player.y).stair:
						was_any_allies = any(m.summon_timer is not None for m in g.monsters)
						time.sleep(0.3)
						g.generate_level()
						g.level += 1
						if was_any_allies:
							g.print_msg("You descend deeper into the dungeon, leaving your summoned allies behind.")
						else:
							g.print_msg("You descend deeper into the dungeon.")	
						for m in player.monsters_in_fov():
							if x_in_y(3, g.level):
								continue
							if dice(1, 20) + calc_mod(player.DEX) - 5 < m.passive_perc:
								m.is_aware = True
					else:
						g.print_msg("You can't go down here.")
					refresh = True
				elif char == "?":
					g.help_menu()
				elif char == ".": #Wait a turn
					player.energy = 0
				elif char == "Q": #Quit
					if g.yes_no("Are you sure you want to quit the game?"):
						g.save_game()
						curses.nocbreak()
						curses.echo()
						exit()
				elif char == "t":
					player.throw_item()
					refresh = True
				elif char == "+": #Display worn rings
					if player.worn_rings:
						num = len(player.worn_rings)
						g.print_msg(f"You are wearing {num} ring{'s' if num != 1 else ''}:")
						g.print_msg(", ".join(r.name for r in player.worn_rings))
						passives = player.calc_ring_passives()
						if passives:
							g.print_msg("Your rings are providing the following passive bonuses:")
							keys = sorted(passives.keys(), key=lambda k: k.lower())
							g.print_msg(", ".join(f"+{passives[k]} {'to-hit' if k == 'to_hit' else k}" for k in keys))
					else:
						g.print_msg("You aren't wearing any rings.")
					refresh = True
			moved = player.energy < lastenergy
			if moved:
				g.do_turn()
				busy = player.resting or player.activity
				if not busy or player.ticks % 10 == 0:
					g.draw_board()
				g.autosave()
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