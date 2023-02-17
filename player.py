import random, time
from utils import *

from entity import Entity
from items import Weapon, UNARMED

class Player(Entity):
	
	def __init__(self, g):
		super().__init__(g)
		self.exp = 0
		self.level = 1
		self.HP = self.MAX_HP
		self.dead = False
		self.ticks = 0
		self.resting = False
		self.weapon = UNARMED
		self.inventory = []
		self.energy = 30
		self.speed = 30
		self.STR = 10
		self.DEX = 10
		self.hp_drain = 0
		self.poison = 0
		self.effects = {}
		self.armor = None
		self.activity = None
		self.did_attack = False
		self.last_attacked = False
		self.moved = False
		self.last_moved = False
		self.grappled_by = []
			
	def add_grapple(self, mon):
		if mon.distance(self) > 1: #Can't grapple if we're not close enough'
			return False
		if mon in self.grappled_by:
			return False
		self.grappled_by.append(mon)
		return True
			
	def remove_grapple(self, mon):
		if mon in self.grappled_by:
			self.grappled_by.remove(mon)
		
	def get_ac_bonus(self, avg=False):
		s = calc_mod(self.DEX, avg)
		if self.armor:
			armor = self.armor
			if armor.dex_mod_softcap is not None:
				softcap = armor.dex_mod_softcap
				if s > softcap: #Reduce any excess above the softcap
					diff = s - softcap
					if avg:
						s = softcap + diff / 4
					else:
						s = softcap + div_rand(diff, 4)
		if self.has_effect("Haste"):
			s += 2
		return s
		
	def get_max_hp(self):
		return max(self.MAX_HP - self.hp_drain, 0)
		
	def get_speed(self):
		speed = self.speed
		if self.has_effect("Haste"):
			speed *= 2
		elif self.has_effect("Lethargy"):
			speed = speed * 2 // 3
		return int(speed)
		
	def max_exp(self):
		return 50 + (self.level - 1) * 20
		
	def gain_exp(self, amount):
		self.exp += amount
		old_level = self.level
		dex_inc = False
		while self.exp >= self.max_exp():
			self.exp -= self.max_exp()
			self.level += 1
			if self.level % 4 == 0:		
				if one_in(2):
					self.STR += 1
				else:
					self.DEX += 1
					dex_inc = True
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
						dex_inc = True
						break
					else:
						self.g.print_msg("Please enter \"S\" or \"D\"")
		if dex_inc and self.armor:
			softcap = self.armor.dex_mod_softcap
			if softcap is not None:
				thresh = 10 + softcap * 2
				if self.DEX >= thresh:
					self.g.print_msg("Note: Any dodge bonus beyond this level of DEX is reduced due to your heavy armor.")	
		if self.level > old_level:
			self.g.print_msg(f"You leveled up to level {(self.level)}!", "green")
		
	@property
	def MAX_HP(self):	
		return 100 + (self.level - 1)*20
	
	def interrupt(self):
		if self.resting:
			self.g.print_msg("Your rest was interrupted.", "yellow")
			self.resting = False
		elif self.activity:
			if not self.g.yes_no(f"Continue {self.activity.name}?"):
				self.g.print_msg(f"You stop {self.activity.name}.")
				self.activity = None
	
	def drain(self, amount):
		if amount <= 0:
			return
		self.hp_drain += amount
		self.HP = min(self.HP, self.get_max_hp())
		self.interrupt()
		if self.get_max_hp() <= 0:
			self.g.print_msg("You have died!", "red")
			self.dead = True	
	
	def do_poison(self, amount):
		if amount <= 0:
			return
		self.poison += amount
		if self.has_effect("Rejuvenated"):
			self.g.print_msg("The rejunenation blocks the effects of the poison in your system.")
		elif self.poison >= self.HP:
			self.g.print_msg("You're lethally poisoned!", "red")
		else:
			self.g.print_msg("You are poisoned!", "yellow")
	
	def take_damage(self, dam, poison=False):
		if dam <= 0:
			return
		self.HP -= dam
		if not poison: #Poison damage should only interrupt activities if it's likely to be lethal
			self.interrupt()
		else:
			if self.poison >= self.HP:
				if self.resting or self.activity:
					self.g.print_msg("The amount of poison in your body is lethal!", "red")
					self.interrupt()
		if self.HP <= 0:
			self.HP = 0
			self.g.print_msg("You have died!", "red")
			self.dead = True
		elif self.HP <= self.get_max_hp() // 4:
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
				if not seeslastpos: #We teleported out of sight
					for m in self.monsters_in_fov():
						m.track_timer = min(m.track_timer, dice(1, 7)) #Allow them to still close in on where they last saw you, and not immediately realize you're gone
				self.g.print_msg("You teleport!")
				self.x = x
				self.y = y
				self.fov = self.calc_fov()
				self.grappled_by.clear()
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
		if self.g.monster_at(self.x + dx, self.y + dy):
			self.moved = True
			self.attack(dx, dy)
			return True
		board = self.g.board
		if not board.is_passable(self.x + dx, self.y + dy):
			return False
		self.moved = True
		if self.grappled_by:
			stat = max(self.DEX, self.STR) #Let's use the higher of the two
			for m in self.grappled_by[:]:
				mod = calc_mod(stat)
				if m.has_effect("Confused"):
					mod += 4 #Give a bonus escaping a confused monster's grab
				if dice(1, 20) + mod >= m.grapple_dc:
					if self.STR > self.DEX or (self.STR == self.DEX and one_in(2)):
						break_method = "force yourself"
					else:
						break_method = "wriggle"
					self.g.print_msg(f"You {break_method} out of the {m.name}'s grapple.")
					self.remove_grapple(m)
					m.energy -= m.get_speed() #So they can't immediately re-grapple the player
				else:
					self.g.print_msg(f"You fail to escape the {m.name}'s grapple.", "yellow")	
			self.energy -= self.get_speed()	
			return True
		if not super().move(dx, dy):
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
			if m.has_effect("Confused") or m.has_effect("Stunned"): #Confused monsters can't make opportunity attacks
				continue
			mon_speed = m.get_speed()
			fuzz = speed//3
			is_faster = mon_speed > speed + random.randint(-fuzz, fuzz)
			if m.is_aware and m.sees_player() and dist >= 2 and is_faster and one_in(3):
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
				
	def lose_effect(self, name, silent=False):
		if name in self.effects:
			eff = self.effects[effect]
			if silent:
				self.g.print_msg(eff.rem_msg)
			del self.effects[effect]
			eff.on_expire(self)
	
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
			
	def stealth_mod(self):
		mod = 0
		if self.last_attacked:
			mod -= 5
		if self.has_effect("Invisible"):
			mod += 5
		if self.armor:
			if self.armor.stealth_pen > 0:
				mod -= self.armor.stealth_pen
		return mod
		
	def knockback(self, dx, dy):
		if dx == 0 and dy == 0:
			return
		self.interrupt()
		board = self.g.board
		newpos = self.x+dx, self.y+dy
		oldpos = (self.x, self.y)
		dist = 0
		for x, y in board.line_between(oldpos, newpos, skipfirst=True):
			if not board.is_passable(x, y):
				if dist > 0:
					dam = dice(2, dist*3)
					self.g.print_msg(f"You take {dam} damage by the impact!", "red")
					self.take_damage(dam)
				return
			if dist == 0:
				self.g.print_msg("You're knocked back!", "red")
			dist += 1
			self.move_to(x, y)
			self.g.draw_board()
			time.sleep(0.01)
		
		
	def throw_item(self):
		throwable = filter(lambda t: isinstance(t, Weapon), self.inventory)
		throwable = filter(lambda t: t.thrown is not None, throwable)
		throwable = list(throwable)
		g = self.g
		if not throwable:
			g.print_msg("You don't have any throwable items.")
			return
		if not (mons := list(self.monsters_in_fov())):
			g.print_msg("You don't see any targets to throw an item.")
			return
		strings = ", ".join(f"{i+1}. {t.name}" for i, t in enumerate(throwable))
		g.print_msg("Throw which item? (Enter a number)")
		g.print_msg(strings)
		try:
			num = int(g.input())
			if num < 1 or num > len(throwable):
				g.print_msg(f"Number must be between 1 and {len(throwable)}.")
				return
		except ValueError:
			g.print_msg("You didn't enter a number.")
			return
		item = throwable[num - 1]
		short, long = item.thrown
		def cond(m): #Here, we take the number of tiles of the LOS line
			dx = abs(self.x - m.x)
			dy = abs(self.y - m.y)
			return max(dx, dy) <= long
		target = g.select_monster_target(cond, error="None of your targets are within range of your {item.name}.")
		if not target:
			return
		g.select = target
		dx = abs(self.x - target.x)
		dy = abs(self.y - target.y)
		num_tiles = max(dx, dy)
		pen = 0
		foe_adjacent = False
		if (m := g.get_monster(self.x-1, self.y)) and m.is_aware and not m.incapacitated():
			foe_adjacent = True
		elif (m := g.get_monster(self.x+1, self.y)) and m.is_aware and not m.incapacitated():
			foe_adjacent = True
		elif (m := g.get_monster(self.x, self.y+1)) and m.is_aware and not m.incapacitated():
			foe_adjacent = True
		elif (m := g.get_monster(self.x, self.y+1)) and m.is_aware and not m.incapacitated():
			foe_adjacent = True
		if foe_adjacent: #If there's a monster who can see us rand is right next to us, it's harder to aim
			pen += 4
		avg_pen = pen
		if num_tiles > short:
			scale = 10
			g.print_msg(f"Ranged accuracy is reduced beyond {short} tiles.", "yellow")
			pen += mult_rand_frac(num_tiles - short, scale, long - short) 
			avg_pen += scale*(num_tiles-short)/(long-short)
		mod = self.attack_mod(avg=False)
		avg_mod = self.attack_mod(avg=True)
		mod -= pen
		avg_mod -= avg_pen
		AC = target.AC
		if target.incapacitated():
			AC = min(AC, 5)
		prob = to_hit_prob(AC, avg_mod)*100
		prob_str = display_prob(prob)
		self.g.print_msg(f"Throwing {item.name} at {target.name} - {prob_str} to-hit.")
		c = g.input("Press enter to throw, or enter \"C\" to cancel")
		g.select = None
		if c and c[0].lower() == "c":
			return
		if g.board.line_of_sight((self.x, self.y), (target.x, target.y)):
			line = list(g.board.line_between((self.x, self.y), (target.x, target.y)))
		else:
			line = list(g.board.line_between((target.x, target.y), (self.x, self.y)))
			line.reverse()
		for x, y in line:
			g.set_projectile_pos(x, y)
			g.draw_board()
			time.sleep(0.03)
		g.clear_projectile()
		roll = dice(1, 20)
		crit = False
		if roll == 1:
			hits = False
		elif roll == 20:
			hits = True
			crit = dice(1, 20) + mod >= AC
		else:
			hits = roll + mod >= AC
		if hits:
			damage = item.roll_dmg()
			if crit:
				damage += item.roll_dmg()
			damage += calc_mod(self.attack_stat())
			damage = target.apply_armor(damage)
			if mon.rubbery:
				if self.weapon.dmg_type == "bludgeon":
					damage = max(0, damage - random.randint(0, mon.HP))
				elif self.weapon.dmg_type == "slash":
					damage = mult_rand_frac(damage, random.randint(250, 750), 1000)
			if damage <= 0:
				if mon.rubbery and self.weapon.dmg_type == "bludgeon":
					g.print_msg(f"The {item.name} harmlessly bounces off the {target.name}.")
				else:
					g.print_msg(f"The {item.name} hits the {target.name} but does no damage.")
			else:
				target.HP -= damage
				msg = f"The {item.name} hits the {target.name} for {damage} damage."
				if target.HP > 0:
					msg += f" Its HP: {target.HP}/{target.MAX_HP}"
				self.g.print_msg(msg)
				if crit:
					self.g.print_msg("Critical!", "green")
				if target.HP <= 0:
					self.defeated_monster(target)
		else:
			g.print_msg(f"The {item.name} misses the {target.name}.")
		g.spawn_item(item.__class__(), (target.x, target.y))	
		if item is self.weapon:
			self.weapon = None
		self.inventory.remove(item)
		self.did_attack = True
		for m in self.monsters_in_fov():
			if m is target or one_in(3):
				m.on_alerted()
		self.energy -= self.speed
			
	def detectability(self):
		d = []
		mons = list(filter(lambda m: not m.is_aware, self.monsters_in_fov()))
		if not mons:
			return None 
		mod = self.stealth_mod() + calc_mod(self.DEX, avg=True)
		total_stealth = 1
		for m in mons:
			perc = m.passive_perc - 5*m.has_effect("Asleep")
			stealth_prob = d20_prob(perc, mod, nat1=True)	
			if not self.last_attacked:
				stealth_prob += (1 - stealth_prob)/2
			total_stealth *= stealth_prob
		#total_stealth is the chance of remaining UNdetected
		#To get the detectability, invert it
		return 1 - total_stealth
		
	def do_turn(self):
		self.last_attacked = self.did_attack
		self.last_moved = self.moved
		self.moved = False
		self.ticks += 1
		for m in self.grappled_by[:]:
			dist = abs(m.x - self.x) + abs(m.y - self.y)
			if dist > 1:
				self.remove_grapple(m)
		if self.poison > 0:
			maxdmg = 1 + self.poison // 8
			dmg = random.randint(1, maxdmg)
			if dmg > self.poison:
				dmg = self.poison
			self.poison -= dmg
			if not self.has_effect("Rejuvenated"): #Rejuvenation allows poison to tick down without doing any damage
				self.take_damage(dmg, True)
				if maxdmg > 3:
					if one_in(2):
						self.g.print_msg("You feel very sick.", "red")
				elif one_in(3):
					self.g.print_msg("You feel sick.", "red")
		elif self.HP < self.get_max_hp():
			if self.ticks % 6 == 0:
				self.HP += 1
		if self.has_effect("Rejuvenated"):
			if self.hp_drain > 0:
				self.hp_drain -= 1
			self.HP += random.randint(4, 8)
			self.HP = min(self.HP, self.get_max_hp())
			if self.ticks % 6 == 0:
				self.g.print_msg("You feel extremely rejuvenated.", "green")
		elif self.ticks % 6 == 0:
			if self.hp_drain > 0 and one_in(4):
				self.hp_drain -= 1
		for e in list(self.effects.keys()):
			self.adjust_duration(e, -1)
		mod = self.stealth_mod()
		for m in self.g.monsters:
			m.check_timer -= 1
			if m.check_timer <= 0 or self.did_attack or one_in(15): #Very occasionally make the check before the timer reaches zero
				m.reset_check_timer()
				if not m.is_aware or self.did_attack: #If you attack while invisible, maybe alert the nearby monsters to your position
					roll = dice(1, 20)
					perc = m.passive_perc
					if m.has_effect("Asleep"):
						perc -= 5
					if (m.x, m.y) in self.fov and (roll == 1 or roll + div_rand(self.DEX - 10, 2) + mod < perc):
						m.on_alerted()
						m.lose_effect("Asleep")
		self.did_attack = False
		
	def attack_stat(self):
		stat = self.STR
		if self.weapon.finesse:
			stat = max(stat, self.DEX)
		return stat
		
	def attack_mod(self, avg=False):
		stat = self.attack_stat()
		mod = calc_mod(stat, avg=avg)
		if self.weapon:
			if self.weapon.heavy:
				mod -= 2
		else:
			mod += 2
		return mod
		
	def base_damage_roll(self):
		w = self.weapon
		return w.roll_dmg() if w else dice(1, 2)
				
	def attack(self, dx, dy):
		x, y = self.x + dx, self.y + dy
		if not self.g.monster_at(x, y):
			self.g.print_msg("You strike at the air.")
			self.energy -= self.get_speed()
			return
		mon = self.g.get_monster(x, y)
		self.energy -= min(self.get_speed(), 45)
		roll = dice(1, 20)
		adv = False
		if not mon.is_aware or self.has_effect("Invisible"):
			adv = True
		finesse = self.weapon.finesse
		unarmed = self.weapon is UNARMED
		sneak_attack = adv and dice(1, 20) + calc_mod(self.DEX) >= mon.passive_perc
		sneak_attack = sneak_attack and x_in_y(3 + finesse - unarmed, 7)
		if mon.has_effect("Asleep"):
			sneak_attack = True	
		if adv:
			roll = max(roll, dice(1, 20))
		crit = False
		eff_ac = mon.AC
		if mon.has_effect("Paralyzed"):
			eff_ac = min(eff_ac, 5)
		mod = self.attack_mod()
		thresh = self.weapon.crit_thresh
		crit_threat = roll >= thresh
		if crit_threat and (roll := dice(1, 20)) + mod >= eff_ac:
			hits = True
			crit = True
		elif roll == 1:
			hits = False
		elif roll == 20:
			hits = True
		else:
			hits = roll + mod >= eff_ac
		if sneak_attack:
			if one_in(3):
				self.g.print_msg(f"The {mon.name} is caught off-guard by your sneak attack!")
			else:
				self.g.print_msg(f"You catch the {mon.name} completely unaware!")
			hits = True
			mon.energy -= 15
		if mon.has_effect("Asleep"):
			hits = True
			mon.lose_effect("Asleep")
		mon.on_alerted()
		if not sneak_attack: #If we did a sneak attack, let's continue to be stealthy
			self.did_attack = True
		if not hits:
			self.g.print_msg(f"Your attack misses the {mon.name}.")
		else:
			stat = self.attack_stat()
			dam = self.base_damage_roll()
			mult = 2
			if self.weapon:
				mult = self.weapon.crit_mult
			if crit:
				for _ in range(mult - 1):
					dam += self.base_damage_roll()
			if sneak_attack:
				scale = 6
				lev = self.level
				if finesse:
					lev = mult_rand_frac(lev, 4, 3)
				val = random.randint(1, lev)
				scale_int = 1 + (val - 1) // scale
				scale_mod = (val - 1) % scale
				bonus = dice(scale_int, 6) + mult_rand_frac(dice(1, 6), scale_mod, scale)
				if unarmed:
					bonus = max(1, div_rand(bonus, 3))
				dam += bonus
			dam += div_rand(stat - 10, 2)
			dam = max(dam, 1)
			dam = mon.apply_armor(dam)
			min_dam = dice(1, 6) if sneak_attack else 0 #Sneak attacks are guaranteed to deal at least 1d6 damage
			dam = max(dam, min_dam)
			if mon.rubbery:
				if self.weapon.dmg_type == "bludgeon":
					dam = max(0, dam - random.randint(0, mon.HP))
				elif self.weapon.dmg_type == "slash":
					dam = mult_rand_frac(dam, random.randint(250, 750), 1000)
			mon.HP -= dam
			if dam > 0:
				msg = f"You hit the {mon.name} for {dam} damage."
				if mon.HP > 0:
					msg += f" Its HP: {mon.HP}/{mon.MAX_HP}"
				self.g.print_msg(msg)
				if crit:
					self.g.print_msg("Critical!", "green")
			elif mon.rubbery and self.weapon.dmg_type == "bludgeon":
				self.g.print_msg(f"You hit the {mon.name} but your attack bounces off of it.")
			else:	
				self.g.print_msg(f"You hit the {mon.name} but do no damage.")
			if mon.HP <= 0:
				self.defeated_monster(mon)
			self.adjust_duration("Invisible", -random.randint(0, 6))
				
	def defeated_monster(self, mon):
		self.g.print_msg(f"The {mon.name} dies!", "green")
		numbefore = len(self.g.monsters)
		self.g.remove_monster(mon)
		numafter = len(self.g.monsters)
		self.remove_grapple(mon)
		val = (mon.diff - 1)**0.85
		gain = math.ceil(min(12 * 2**val, 60 * 1.5**val) - 6)
		self.gain_exp(gain)
		if mon.weapon:
			if isinstance(mon.weapon, list):
				for w in mon.weapon:
					if one_in(3):
						weapon = w()
						self.g.print_msg(f"The {mon.name} drops its {weapon.name}!", "green")
						self.g.spawn_item(weapon, (mon.x, mon.y))
			elif one_in(3):
				weapon = mon.weapon()
				self.g.print_msg(f"The {mon.name} drops its {weapon.name}!", "green")
				self.g.spawn_item(weapon, (mon.x, mon.y))
		if numbefore > 0 and numafter == 0:
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
				if tile.items:
					continue
				tile.symbol = ">"
				tile.stair = True
				break
		