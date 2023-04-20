import random, time, math
from collections import defaultdict
from utils import *

from entity import Entity
from items import *
from os import get_terminal_size

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
		
		self.base_str = 10
		self.base_dex = 10
		self.mod_str = 0
		self.mod_dex = 0
		self.str_drain = 0
		self.dex_drain = 0
		self.passives = defaultdict(int)
		
		self.hp_drain = 0
		self.poison = 0
		self.fire = 0
		self.turns_engulfed = 0 #For the water elemental
		self.engulfed_by = None
		self.effects = {}
		self.armor = None
		self.activity = None
		self.did_attack = False
		self.last_attacked = False
		self.moved = False
		self.last_moved = False
		
		self.grappled_by = []
		self.worn_rings = []
		
	def calc_ring_passives(self):
		passives = defaultdict(int)
		for ring in self.worn_rings:
			for stat, val in ring.passives.items():
				passives[stat] += val**2
		for p in passives:
			passives[p] = math.ceil(round(math.sqrt(passives[p]), 3))
		return passives
		
	def recalc_passives(self):
		passives = self.calc_ring_passives()
		self.passives = passives

	#Todo: Allow effects to modify these values
		
	@property
	def STR(self):
		return self.base_str + self.mod_str
		
	@property
	def DEX(self):
		return self.base_dex + self.mod_dex
			
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
		s += self.passives["dodge"]
		s -= 2 * len(self.grappled_by)
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
		return 50 + math.ceil((self.level - 1)**1.2 * 20)
		
	def gain_exp(self, amount):
		self.exp += amount
		old_level = self.level
		dex_inc = False
		while self.exp >= self.max_exp():
			self.exp -= self.max_exp()
			self.level += 1
			avg = (self.base_str+self.base_dex)//2
			past_softcap = avg >= 20
			if self.level % (4+2*past_softcap) == 0:
				if one_in(2):
					self.base_str += 1
				else:
					self.base_dex += 1
					dex_inc = True
			if self.level % (3+past_softcap) == 0:
				self.g.print_msg(f"You leveled up to level {(self.level)}!", "green")
				old_level = self.level
				while True:
					user = self.g.input("Would you like to increase (S)TR or (D)EX?")
					user = user.upper()
					if user == "S":
						self.base_str += 1
						break
					elif user == "D":
						self.base_dex += 1
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
	
	def interrupt(self, force=False):
		if self.resting:
			self.g.print_msg("Your rest was interrupted.", "yellow")
			self.resting = False
		elif self.activity:
			if force or not self.g.yes_no(f"Continue {self.activity.name}?"):
				self.g.print_msg(f"You stop {self.activity.name}.")
				self.activity = None
	
	def drain(self, amount, silent=False):
		if amount <= 0:
			return
		self.hp_drain += amount
		self.HP = min(self.HP, self.get_max_hp())
		if not silent:
			self.g.print_msg("Your life force is drained!", "red")
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
	
	def take_damage(self, dam, poison=False, force_interrupt=False):
		if dam <= 0:
			return
		self.HP -= dam
		if force_interrupt:
			self.interrupt(force=True)
		elif not poison: #Poison damage should only interrupt activities if it's likely to be lethal
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
	
	def add_item(self, item):
		if isinstance(item, Wand):
			w = next((t for t in self.inventory if isinstance(t, Wand) and type(t) == type(item)), None)
			if w is not None:
				w.charges += item.charges
			else:
				self.inventory.append(item)
		else:
			self.inventory.append(item)
			
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
	
	def grapple_check(self):
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
		return False
	
	def move(self, dx, dy):
		if self.dead:
			self.energy = 0
			return False
		board = self.g.board
		if self.has_effect("Confused") and not one_in(4):
			odx, ody = dx, dy
			dirs = [(-1, 0), (1, 0), (0, 1), (0, -1)]
			for _ in range(2):
				dx, dy = random.choice(dirs)
				if board.is_passable(self.x+dx, self.y+dy):
					break
			if not board.is_passable(self.x+dx, self.y+dy):
				x, y = self.x + dx, self.y + dy
				obstacle = ""
				if board.blocks_sight(x, y):
					obstacle = "wall"
				elif (m := self.g.get_monster(x, y)):
					obstacle = m.name
				if obstacle:
					self.g.print_msg(f"You bump into the {obstacle}.")
					self.energy -= self.get_speed()#We bumped into something while confused
					return
			if one_in(3) and (odx, ody) != (dx, dy):
				self.g.print_msg("You stumble around.")
		adj = []
		if (m := self.g.get_monster(self.x-1, self.y)):
			adj.append(m)
		if (m := self.g.get_monster(self.x+1, self.y)):
			adj.append(m)
		if (m := self.g.get_monster(self.x, self.y+1)):
			adj.append(m)
		if (m := self.g.get_monster(self.x, self.y+1)):
			adj.append(m)
		if (m := self.g.get_monster(self.x + dx, self.y + dy)):
			self.moved = True
			if m.is_friendly():
				if self.grapple_check():
					return
				self.energy -= 30
				self.swap_with(m)
				m.energy = min(m.energy - 30, 0)
				self.g.print_msg(f"You swap places with the {m.name}.")
			else:
				self.attack(dx, dy)
			return True
		board = self.g.board
		if not board.is_passable(self.x + dx, self.y + dy):
			return False
		self.moved = True
		if self.grapple_check():
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
			if m.is_friendly():
				continue
			mon_speed = m.get_speed()
			fuzz = speed//3
			is_faster = mon_speed > speed + random.randint(-fuzz, fuzz)
			if m.is_aware and m.sees_player() and dist >= 2 and is_faster and one_in(3):
				self.g.print_msg(f"As you move away from {m.name}, it makes an opportunity attack!", "yellow")
				m.melee_attack(target=self)
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
		
	def sees(self, pos, clairv=False):
		clairv = clairv and self.has_effect("Clairvoyance")
		if pos in self.fov:
			return True
		elif clairv:
			x, y = pos
			dx = self.x - x 
			dy = self.y - y
			dist = math.sqrt(dx**2 + dy**2)
			return round(dist) <= 8
		else:
			return False
		
	def monsters_in_fov(self, include_friendly=False, clairvoyance=False):
		if clairvoyance:
			clairvoyance = self.has_effect("Clairvoyance")
		for m in self.g.monsters:
			if not include_friendly and m.is_friendly():
				continue
			mx, my = m.x, m.y
			dx = self.x - mx 
			dy = self.y - my
			dist = math.sqrt(dx**2 + dy**2)
			if (mx, my) in self.fov or (clairvoyance and round(dist) <= 8):
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
		mod = self.passives["stealth"]
		if self.last_attacked:
			mod -= 5
		if self.has_effect("Invisible"):
			mod += 5
		if self.armor:
			if self.armor.stealth_pen > 0:
				mod -= self.armor.stealth_pen
		return mod
		
	def knockback_from(self, ox, oy, force):
		if force <= 0:
			return
		dx = self.x - ox
		dy = self.y - oy
		if dx != 0:
			dx //= abs(dx)
		if dy != 0:
			dy //= abs(dy)
		dx *= force
		dy *= force
		self.knockback(dx, dy)
		
	def knockback(self, dx, dy):
		if dx == 0 and dy == 0:
			return
		board = self.g.board
		newpos = self.x+dx, self.y+dy
		oldpos = (self.x, self.y)
		dist = 0
		self.grappled_by.clear()
		for x, y in board.line_between(oldpos, newpos, skipfirst=True):
			if not board.is_passable(x, y):
				if dist > 0:
					if (m := self.g.get_monster(x, y)) is not None:
						dam = dice(1, dist*3)
						self.g.print_msg(f"You take {dam} damage by the impact!", "red")
						self.take_damage(dam)
						amount = max(1, binomial(dam, 50))
						self.g.print_msg(f"The {m.name} takes {dam} damage from your impact!")
						m.take_damage(dam, source=self)
						self.energy -= 15
						m.energy -= 15
					else:
						dam = dice(2, dist*3)
						self.g.print_msg(f"You take {dam} damage by the impact!", "red")
						self.take_damage(dam)
						self.energy -= 30
				return
			if dist == 0:
				self.g.print_msg("You're knocked back!", "red")
				self.interrupt(force=True)
			dist += 1
			self.move_to(x, y)
			self.g.draw_board()
			time.sleep(0.01)
		
		
	def throw_item(self, item):
		g = self.g
		if not (mons := list(self.monsters_in_fov())):
			g.print_msg("You don't see any targets to throw an item.")
			return
		if item.thrown:
			short, long = item.thrown
		else:
			short, long = 4, 12
		def cond(m): #Here, we take the number of tiles of the LOS line
			dx = abs(self.x - m.x)
			dy = abs(self.y - m.y)
			return max(dx, dy) <= long
		target = g.select_monster_target(cond, error=f"None of your targets are within range of your {item.name}.")
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
		if foe_adjacent: #If there's a monster who can see us and is right next to us, it's harder to aim
			pen += 3
		avg_pen = pen
		if num_tiles > short:
			scale = 8
			g.print_msg(f"Ranged accuracy is reduced beyond {short} tiles.", "yellow")
			pen += mult_rand_frac(num_tiles - short, scale, long - short) 
			avg_pen += scale*(num_tiles-short)/(long-short)
		if item.heavy:
			pen += 2
			g.print_msg(f"This weapon is heavy, so accuracy is reduced.", "yellow")
		if not item.thrown:
			pen += 2
			g.print_msg(f"This weapon isn't designed to be thrown, so accuracy is reduced.", "yellow")
		mod = self.attack_mod(throwing=False, avg=False)
		avg_mod = self.attack_mod(throwing=False, avg=True)
		mod -= pen
		avg_mod -= avg_pen
		AC = target.get_ac()
		avg_AC = target.get_ac(avg=True)
		if target.incapacitated():
			AC = min(AC, 5)
			avg_AC = min(avg_AC, 5)
		prob = to_hit_prob(avg_AC, avg_mod)*100
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
		else:
			hits = roll + mod >= AC
		if hits:
			if x_in_y(item.crit_chance, 20):
				crit = True
			dmg = item.dmg
			damage = dmg.roll()
			damage += calc_mod(self.attack_stat())
			damage += item.enchant
			if not item.thrown:
				damage = random.randint(1, damage)
			if crit:
				bonus = 0
				for _ in range(item.crit_mult - 1):
					bonus += dmg.roll()
				if not item.thrown:
					bonus = random.randint(1, bonus)
				damage += bonus
			damage = target.apply_armor(damage, 1+crit) #Crits give 50% armor penetration
			if damage <= 0:
				g.print_msg(f"The {item.name} hits the {target.name} but does no damage.")
			else:
				msg = f"The {item.name} hits the {target.name} for {damage} damage."
				if target.HP > damage: #Only print the HP message if the attack didn't kill them
					msg += f" Its HP: {target.HP-damage}/{target.MAX_HP}"
				self.g.print_msg(msg)
				if crit:
					self.g.print_msg("Critical!", "green")
				target.take_damage(damage, self)
		else:
			g.print_msg(f"The {item.name} misses the {target.name}.")
		g.spawn_item(item.__class__(), (target.x, target.y))	
		if item is self.weapon:
			self.weapon = UNARMED
		
		self.inventory.remove(item)
		self.did_attack = True
		for m in self.monsters_in_fov():
			if m is target:
				if not m.despawn_summon():
					m.on_alerted()
			elif one_in(3):
				m.on_alerted()
		cost = 30
		if not item.thrown:
			cost *= 2 if item.heavy else 1.5
		self.energy -= cost
		
	def is_unarmed(self):
		return self.weapon is UNARMED
			
	def detectability(self):
		d = []
		mons = list(filter(lambda m: not m.is_aware, self.monsters_in_fov()))
		if not mons:
			return None 
		mod = self.stealth_mod() + calc_mod(self.DEX, avg=True)
		total_stealth = 1
		for m in mons:
			perc = m.passive_perc - 5*m.has_effect("Asleep")
			stealth_prob = d20_prob(perc, mod)	
			stealth_prob *= 1 - 1/30 #Includes the 1/30 auto-fail chance
			if not self.last_attacked:
				stealth_prob += (1 - stealth_prob)/2.5
			total_stealth *= stealth_prob
		#total_stealth is the chance of remaining UNdetected
		#To get the detectability, invert it
		return 1 - total_stealth
		
	def do_turn(self):
		self.last_attacked = self.did_attack
		self.last_moved = self.moved
		self.moved = False
		
		self.mod_str = 0
		self.mod_dex = 0
		
		#Passive modifiers go here
		self.mod_str += self.passives["STR"] - self.str_drain
		self.mod_dex += self.passives["DEX"] - self.dex_drain	

		self.ticks += 1
		for m in self.grappled_by[:]:
			dist = abs(m.x - self.x) + abs(m.y - self.y)
			if dist > 1:
				self.remove_grapple(m)
		can_regen = self.poison <= 0 and self.fire <= 0
		if self.poison > 0:
			dmg = 1 + math.isqrt(self.poison//2)
			if dmg > self.poison:
				dmg = self.poison
			self.poison -= dmg
			if not self.has_effect("Rejuvenated"): #Rejuvenation allows poison to tick down without doing any damage
				self.take_damage(dmg, True)
				if dmg > 3:
					if one_in(2):
						self.g.print_msg("You feel very sick.", "red")
				elif one_in(3):
					self.g.print_msg("You feel sick.", "red")
		if self.engulfed_by:
			if self.engulfed_by in self.grappled_by:
				self.turns_engulfed += 1
				if self.fire > 0:
					self.fire -= 1
					if self.fire <= 0:
						self.g.print_msg("The water extinguishes the fire.")
				if self.turns_engulfed > 1:
					self.g.print_msg("You can't breathe, as you are engulfed by the water!", "red")
					amount = 3 + (self.turns_engulfed - 1)**0.7
					self.take_damage(div_rand(int(100*amount), 100))
			else:
				self.turns_engulfed = 0
				self.engulfed_by = None
		if self.fire > 0:
			self.g.print_msg("The fire burns you!", "red")
			dmg = dice(1, 10)+2
			self.take_damage(dmg, force_interrupt=True) #Always interrupt activities for this
			if self.ticks % 2 == 0 and dice(1, 20) + calc_mod(self.DEX) >= 10:
				self.fire -= 1
				if self.fire <= 0:
					self.g.print_msg("You manage to fully extinguish the fire.", "green")
		if can_regen and self.HP < self.get_max_hp():
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
				if self.hp_drain == 0:
					self.g.print_msg("You have fully recovered from drain.", "green")
		recover = 3 if self.has_effect("Rejuvenated") else 20
		if self.ticks % recover == 0:
			if self.str_drain > 0 and one_in(recover):
				self.str_drain -= 1
			if self.dex_drain > 0 and one_in(recover):
				self.dex_drain -= 1
		for e in list(self.effects.keys()):
			self.adjust_duration(e, -1)
		mod = self.stealth_mod()
		for m in self.g.monsters:
			m.check_timer -= 1
			if m.check_timer <= 0 or self.did_attack or one_in(25): #Very occasionally make the check before the timer reaches zero
				m.reset_check_timer()
				if not m.is_aware or self.did_attack: #If you attack while invisible, maybe alert the nearby monsters to your position
					roll = dice(1, 20)
					perc = m.passive_perc
					if m.has_effect("Asleep"):
						perc -= 5
					if (m.x, m.y) in self.fov and (one_in(30) or roll + div_rand(self.DEX - 10, 2) + mod < perc):
						m.on_alerted()
						m.lose_effect("Asleep")
		self.did_attack = False
		
	def attack_stat(self):
		stat = self.STR
		if self.weapon.finesse:
			stat = max(stat, self.DEX)
		return stat
		
	def attack_mod(self, throwing=False, avg=False):
		stat = self.attack_stat()
		mod = calc_mod(stat, avg=avg)
		if not throwing:
			if self.weapon is not UNARMED:
				if self.weapon.heavy:
					mod -= 2
			else:
				mod += 2
			mod += self.weapon.enchant
		return mod + self.passives["to_hit"]
		
	def base_damage_dice(self):
		return self.weapon.dmg
		
	def apply_resist(self, dam):
		if self.has_effect("Resistance"):
			dam = binomial(dam, 50)
		return dam
		
	def get_protect(self):
		protect = self.armor.protect if self.armor else 0
		protect += self.passives["protect"]
		return protect
		
	def protect_roll(self):
		prot = self.get_protect()
		roll1 = random.randint(0, 4*prot)
		roll2 = random.randint(0, 2*prot)
		return max(roll1, roll2)
		
	def apply_armor(self, dam):
		return max(0, dam - self.protect_roll()) 
		
	def attack(self, dx, dy):
		x, y = self.x + dx, self.y + dy
		if not self.g.monster_at(x, y):
			self.g.print_msg("You strike at the air.")
			self.energy -= self.get_speed()
			return
		mon = self.g.get_monster(x, y)
		ench_type = self.weapon.ench_type
		cost = min(self.get_speed(), 45)
		if ench_type == "speed":
			cost = div_rand(cost, 2)
		self.energy -= cost
		roll = dice(1, 20)
		adv = False
		if not mon.is_aware or self.has_effect("Invisible"):
			adv = True
		finesse = self.weapon.finesse
		unarmed = self.weapon is UNARMED
		sneak_attack = adv and dice(1, 20) + calc_mod(self.DEX) + self.passives["stealth"] >= mon.passive_perc
		chance = 3
		if unarmed:
			chance -= 1
		elif finesse:
			chance += 1
		sneak_attack = sneak_attack and x_in_y(chance, 8)
		if mon.has_effect("Asleep"):
			sneak_attack = True
		eff_ac = mon.get_ac()
		if mon.has_effect("Paralyzed"):
			eff_ac = min(eff_ac, 5)
			adv = True
		if adv:
			roll = max(roll, dice(1, 20))
		crit = False
		mod = self.attack_mod()
		if roll == 1:
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
			mon.energy -= random.randint(15, 30)
		if mon.has_effect("Asleep"):
			hits = True
			mon.lose_effect("Asleep")
		mon.on_alerted()
		if not sneak_attack: #If we did a sneak attack, let's continue to be stealthy
			self.did_attack = True
		if not hits:
			self.g.print_msg(f"Your attack misses the {mon.name}.")
		else:
			if x_in_y(self.weapon.crit_chance, 20):
				crit = True
			stat = self.attack_stat()
			dmgdice = self.base_damage_dice()
			dam = dmgdice.roll()
			mult = self.weapon.crit_mult
			if crit:
				for _ in range(mult - 1):
					dam += dmgdice.roll()
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
				softcap = dmgdice.avg()*mult
				if bonus > softcap: #Adds a soft cap to sneak attack damage
					diff = bonus - softcap
					bonus = softcap + div_rand(diff, 3)
				dam += bonus
			dam += div_rand(stat - 10, 2)
			dam += self.weapon.enchant
			dam = max(dam, 1)
			dam = mon.apply_armor(dam, 1+crit)
			if ench_type == "armor piercing":
				dam2 = mon.apply_armor(dam, 1+crit)
				if dam < dam2:
					dam = dam2
			min_dam = dice(1, 6) if sneak_attack else 0 #Sneak attacks are guaranteed to deal at least 1d6 damage
			dam = max(dam, min_dam)
			dmgtype = self.weapon.dmg_type
			if dam > 0:
				msg = f"You hit the {mon.name} for {dam} damage."
				if mon.HP > dam:
					msg += f" Its HP: {mon.HP-dam}/{mon.MAX_HP}"
				self.g.print_msg(msg)
				if crit:
					self.g.print_msg("Critical!", "green")
			else:	
				self.g.print_msg(f"You hit the {mon.name} but do no damage.")
			if dam > 0 and ench_type == "life stealing" and one_in(7):
				base = dam
				fuzz = (base+1//2)
				base += random.randint(0, fuzz) - random.randint(0, fuzz)
				stolen = min(dice(4, 4), base)
			
				if stolen > 0:
					self.g.print_msg(f"You steal an additional {stolen} HP.", "green")
					dam += stolen
			mon.take_damage(dam, self)
			
			self.adjust_duration("Invisible", -random.randint(0, 6))
			if not sneak_attack:
				for m in self.monsters_in_fov():
					d = m.distance(self, False)
					if one_in(6) or one_in(d):
						m.on_alerted()
			
	def defeated_monster(self, mon):
		self.g.print_msg(f"The {mon.name} dies!", "green")
		self.g.remove_monster(mon)
		num = len(list(filter(lambda m: not m.is_friendly(), self.g.monsters)))
		self.remove_grapple(mon)
		d = mon.diff
		if d > 4:
			d = 4 + (mon.diff - 4) / 2
		v1 = min(d, 6*math.log2(1+d/6))
		val = (v1 - 1)**0.85
		gain = math.ceil(12 * 2**val) - 6
		self.gain_exp(gain)
		if mon.weapon:
			if isinstance(mon.weapon, list):
				for w in mon.weapon:
					if one_in(4):
						weapon = w()
						self.g.print_msg(f"The {mon.name} drops its {weapon.name}!", "green")
						self.g.spawn_item(weapon, (mon.x, mon.y))
			elif one_in(4):
				weapon = mon.weapon()
				self.g.print_msg(f"The {mon.name} drops its {weapon.name}!", "green")
				self.g.spawn_item(weapon, (mon.x, mon.y))
		if num == 0:
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
	
	def inventory_menu(self):
		from gameobj import GameTextMenu
		menu = GameTextMenu(self.g)
		max_lines = get_terminal_size().lines	
		scroll = 0
		items = self.inventory[:]
		d = {}
		for item in items:
			name = item.name
			if isinstance(item, Wand):
				name += f" - {item.charges} charges"
			elif isinstance(item, Ring) and item in self.worn_rings:
				name += " (worn)"
			elif isinstance(item, Weapon) and item is self.weapon:
				name += " (wielded)"
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
			strings.append(n)
			choices.append(item)
		shown_return_msg = False
		chars = "1234567890abcdefghijklmnop"
		while True:
			menu.clear_msg()
			menu.add_text("Select which item?")
			menu.add_text("Use the w and s keys to scroll, press Enter to cancel")
			menu.add_line()
			num_display = min(len(chars), max_lines - 4)
			scroll_limit = max(0, len(strings) - num_display)
			n = min(len(strings), num_display)
			padsize = min(30, get_terminal_size().columns)
			for i in range(n):
				string = strings[i+scroll].ljust(padsize)
				if i == 0 and scroll > 0:
					string += " (↑)"
				if i == n - 1 and scroll < scroll_limit:
					string += " (↓)"
				menu.add_text(f"{chars[i]} - {string}")
			menu.add_line()
			menu.display()
			choice = menu.getch()
			char = chr(choice)
			if char == "w":
				if scroll > 0:
					scroll -= 1
			elif char == "s":
				scroll += 1	
				if scroll > scroll_limit:
					scroll = scroll_limit
			elif choice == 10: #Enter:
				break
			elif char in chars:
				ind = chars.index(char) 
				if ind < num_display:
					item = choices[ind+scroll]
					menu.clear_msg()
					menu.add_text(item.name)
					menu.add_line()
					menu.add_text(item.description)
					if isinstance(item, Weapon):
						dmg = item.dmg
						X, Y = dmg.num, dmg.sides
						menu.add_text(f"This weapon deals {X}d{Y} base damage.")
						if item.heavy:
							menu.add_text("This weapon is heavy, so attacks are a bit less accurate.")
						if item.finesse:
							menu.add_text("This weapon is designed in a way that allows it to adapt to your character's style. Attack and damage rolls use the higher of your STR or DEX.")
						if item.crit_chance > 1:
							menu.add_text(f"Base critical chance on a hit with this weapon is {item.crit_chance}x higher.")
						if item.crit_mult > 2:
							menu.add_text(f"This weapon deals {item.crit_mult}x damage on a critical hit.")
					elif isinstance(item, Armor):
						if item.stealth_pen > 0:
							menu.add_text(f"This armor tends to make some noise when moving. -{item.stealth_pen} to stealth checks.")
					menu.add_line()
					can_throw = isinstance(item, Weapon)
					use_disp = "use item"
					if isinstance(item, Weapon):
						if item is self.weapon:
							use_disp = "unwield"
						else:
							use_disp = "wield"
					menu.add_text(f"u - {use_disp}") #TODO: Combine the "Throw" menu into this menu and remove the "t" keybind
					if can_throw:
						menu.add_text("t - throw") 
					menu.add_text("Enter - return")
					menu.display()
					while True:
						c = menu.getch()
						if c == 10:
							break
						elif chr(c) == "u":
							menu.close()
							result = item.use(self)
							if result is not False: #False to not use time up a turn or the item
								if result is not None: #None uses a turn without removing the item
									self.inventory.remove(item)
								self.energy -= self.get_speed()
							return
						elif chr(c) == "t" and can_throw:
							menu.close()
							self.throw_item(item)
							return
		menu.close()
	