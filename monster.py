import random
from utils import *
from entity import Entity
from items import *

class Attack:
	
	def __init__(self, dmg, to_hit, msg="The {0} attacks you"):
		self.dmg = dmg
		self.to_hit = to_hit
		self.msg = msg
		
	def can_use(self, mon, player):
		return True	
		
	def on_hit(self, player, mon, dmg):
		pass
	
symbols = {}
dup_warnings = []
								
class Monster(Entity):
	min_level = 1
	speed = 30
	diff = 1
	AC = 10
	to_hit = 0
	passive_perc = 11
	WIS = 10
	grapple_dc = 10
	armor = 0
	attacks = [Attack((1, 3), 0)]
	beast = True
	symbol = "?"
	weapon = None
	
	#Monster traits
	rubbery = False
	
	def __init__(self, g, name="monster", HP=10, ranged=None, ranged_dam=(2, 3)):
		super().__init__(g)
		if ranged is None:
			ranged = one_in(5)
		self.HP = HP
		self.MAX_HP = HP
		self.name = name
		self.ranged = ranged
		self.last_seen = None
		self.dir = None
		self.ranged_dam = ranged_dam
		self.track_timer = 0
		self.is_aware = False
		self.check_timer = 1
		self.effects = {}
		self.summon_timer = None
		self.energy = -random.randrange(self.speed)
		self.target = None
		
	def is_friendly(self):
		if self.has_effect("Charmed"):
			return True
		return self.summon_timer is not None
		
	def despawn(self):
		self.HP = 0
		self.energy = -self.get_speed()
		self.g.remove_monster(self)
		
	def __init_subclass__(cls):
		if cls.symbol in symbols:
			other = symbols[cls.symbol] 
			dup_warnings.append(f"{cls.__name__} has same symbol as {other.__name__}")
		else:
			symbols[cls.symbol] = cls
				
	def get_speed(self):
		speed = self.speed
		#When effects modify speed, the effects will go here
		return speed
		
	def reset_check_timer(self):
		self.check_timer = random.randint(1, 3)
	
	def move(self, dx, dy):
		if super().move(dx, dy):
			self.energy -= 30
			return True
		return False
		
	def choose_polymorph_type(self):
		#Note: A bit of a hack using object polymorphing
		types = Monster.__subclasses__()
		candidates = list(filter(lambda typ: typ.diff <= self.diff and typ.beast and typ != self.__class__, types))
		assert len(candidates) > 0
		tries = 100
		while tries > 0:
			tries -= 1
			maxdiff = max(1, self.diff - one_in(2))
			newdiff = 1
			for _ in range(random.randint(2, 3)):
				newdiff = random.randint(newdiff, maxdiff)
			choices = list(filter(lambda typ: newdiff == typ.diff, candidates))
			if not choices:
				continue 
			chosen = random.choice(choices)
			if one_in(6):
				return chosen
			inst = chosen(self.g)
			if inst.MAX_HP < self.MAX_HP:
				if chosen.armor <= self.armor or one_in(2):
					return chosen
		return random.choice(candidates)		
		
	def polymorph(self):
		oldname = self.name
		typ = self.choose_polymorph_type()
		self.__class__ = typ
		inst = typ(self.g)
		self.ranged = False
		self._symbol = inst.symbol
		self.HP = inst.HP
		self.MAX_HP = inst.MAX_HP
		self.name = inst.name
		a_an = "an" if self.name[0] in "aeiou" else "a"
		self.g.print_msg_if_sees((self.x, self.y), f"The {oldname} polymorphs into a {self.name}!")
					
	def has_effect(self, name):
		return name in self.effects
		
	def lose_effect(self, name):
		if name in self.effects:
			del self.effects[name]
			
	def incapacitated(self):
		incap_effs = ["Asleep", "Stunned", "Paralyzed"]
		for e in incap_effs:
			if self.has_effect(e):
				return True
		return False
		
	def gain_effect(self, name, duration):
		if name not in self.effects:
			self.effects[name] = 0
		self.effects[name] += duration
		if self.incapacitated():
			player = self.g.player
			player.remove_grapple(self)
		
	def lose_effect(self, name):
		if name in self.effects:
			del self.effects[name]
			
	def despawn_summon(self):
		if self.summon_timer is None:
			return False
		self.despawn()
		self.g.print_msg_if_sees((self.x, self.y), "Your summoned ally disappears!")
		return True
		
	def take_damage(self, dam, source=None):
		self.HP -= dam
		if source is self.g.player and self.despawn_summon():
			return
		if self.HP <= 0:
			self.despawn()
			if source is not None:
				if source is self.g.player or source.is_friendly():
					self.g.player.defeated_monster(self)
				else:
					self.despawn_summon()
					
	def do_turn(self):
		self.energy += self.get_speed()
		while self.energy > 0:
			old = self.energy
			self.actions()
			if self.energy == old:
				self.energy = min(self.energy, 0) 
		self.tick_effects()
			
	def tick_effects(self):
		if self.summon_timer is not None and self.summon_timer > 0:
			self.summon_timer -= 1
			if self.summon_timer == 0:
				self.despawn()
				self.g.print_msg_if_sees((self.x, self.y), "Your summoned ally disappears!")
				return
		if self.track_timer > 0:
			self.track_timer -= 1
		for e in list(self.effects.keys()):
			self.effects[e] -= 1
			if self.effects[e] <= 0:
				del self.effects[e]
				if e == "Confused":
					self.g.print_msg_if_sees((self.x, self.y), f"The {self.name} is no longer confused.")
				elif e == "Stunned":
					self.g.print_msg_if_sees((self.x, self.y), f"The {self.name} is no longer stunned.")
				elif e == "Frightened":
					self.g.print_msg_if_sees((self.x, self.y), f"The {self.name} regains courage.")
				elif e == "Charmed":
					self.g.print_msg_if_sees((self.x, self.y), f"The {self.name} becomes hostile again!", "yellow")
					self.energy -= self.get_speed()
					self.target = self.g.player
				
	def should_use_ranged(self):
		board = self.g.board
		player = self.g.player
		if not self.has_line_of_fire():
			return False
		return x_in_y(2, 5)
		
	def modify_damage(self, target, damage):
		player = self.g.player
		armor = target.armor
		if armor:
			if target is player:
				damage -= random.randint(1, armor.protect*4) #Armor can reduce damage
			else:
				damage -= random.randint(0, mult_rand_frac(armor, 3, 2))
			if damage <= 0:
				return 0
		if target is player and player.has_effect("Resistance"):
			damage = binomial(damage, 50)
		return max(damage, 0)
		
	def melee_attack(self, target=None, attack=None, force=False):
		if attack is None:
			attacks = list(filter(lambda a: isinstance(a, list) or a.can_use(self, self.g.player), self.attacks))
			if not attacks:
				return
			attack = random.choice(attacks)
			if isinstance(attack, list):
				c = list(filter(lambda a: a.can_use(self, self.g.player), attack))
				attack = random.choice(c)
		player = self.g.player
		if target is None:
			target = player
		roll = dice(1, 20)
		disadv = 0
		disadv += target.has_effect("Invisible")
		disadv += self.has_effect("Frightened") and self.sees_player()
		for _ in range(disadv):
			roll = min(roll, dice(1, 20))
		if target is player:
			ac_mod = player.get_ac_bonus()
			AC = 10 + ac_mod - 2 * len(player.grappled_by)
		else:
			AC = target.AC
			mon = target
			mon.target = self
		bonus = attack.to_hit
		total = roll + bonus
		if roll == 1:
			hits = False
		elif roll == 20:
			hits = True
		else:
			hits = total >= AC
		
		if not hits:
			if target is not player or roll == 1 or total < AC - ac_mod:
				the_target = "you" if target is player else f"the {target.name}"
				self.g.print_msg_if_sees((target.x, target.y), f"The {self.name}'s attack misses {the_target}.")
			else:
				self.g.print_msg(f"You evade the {self.name}'s attack.")
		else:
			damage = self.modify_damage(target, dice(*attack.dmg))
			the_target = "you" if target is player else f"the {target.name}"
			if damage:		
				self.g.print_msg_if_sees((target.x, target.y), attack.msg.format(self.name, the_target) + f" for {damage} damage!", "red" if target is player else "white")
				if target is player:
					target.take_damage(damage)
					attack.on_hit(player, self, damage)
				else:
					target.take_damage(damage, source=self)
			else:
				self.g.print_msg_if_sees((target.x, target.y), attack.msg.format(self.name, the_target) + " but does no damage.")
			
	def do_melee_attack(self, target=None):
		player = self.g.player
		if target is not None:
			target = player
		for att in self.attacks:
			if isinstance(att, list):
				attacks = list(filter(lambda a: a.can_use(self, self.g.player), att))
				if not attacks:
					continue
				att = random.choice(attacks)
			if att.can_use(self, player):
				self.melee_attack(player, att)
		
	def do_ranged_attack(self, target=None):
		if not self.ranged:
			return
		player = self.g.player
		board = self.g.board
		if target is None:
			target = player
		the_target = "you" if target is player else f"the {target.name}"
		self.g.print_msg(f"The {self.name} makes a ranged attack at {the_target}.")
		for point in board.line_between((self.x, self.y), (target.x, target.y), skipfirst=True, skiplast=True):
			self.g.set_projectile_pos(*point)
			self.g.draw_board()
			time.sleep(0.08)
		self.g.clear_projectile()
		roll = dice(1, 20)
		if (target is player and player.has_effect("Invisible")) or self.has_effect("Frightened"): #The player is harder to hit when invisible
			roll = min(roll, dice(1, 20))
		bonus = self.to_hit
		if target is player:
			dodge_mod = player.get_ac_bonus()
			AC = 10 + dodge_mod - 2 * len(player.grappled_by)
		else:
			AC = target.AC
		total = roll + self.to_hit
		if roll == 1:
			hits = False
		elif roll == 20:
			hits = True
		else:
			hits = total >= AC
		if not hits:
			if target is player and roll > 1 and total >= AC - dodge_mod:
				self.g.print_msg("You dodge the projectile.")
			else:
				self.g.print_msg(f"The projectile misses {the_target}.")
		else:
			damage = self.modify_damage(target, dice(*self.ranged_dam))
			if damage:
				the_target_is = "You are" if target is player else "The {target.name} is"
				self.g.print_msg(f"{the_target_is} hit for {damage} damage!", "red" if target is player else "white")
				player.take_damage(damage)
			else:
				self.g.print_msg(f"The projectile hits {the_target} but does no damage.")
		self.energy -= self.get_speed()
			
	def sees_player(self):
		player = self.g.player
		if player.has_effect("Invisible"):
			return False
		return (self.x, self.y) in player.fov
	
	def can_guess_invis(self):
		#Can we correctly guess the player's exact position when invisible?
		player = self.g.player
		xdist = player.x - self.x
		ydist = player.y - self.y
		dist = abs(xdist) + abs(ydist)
		if dist <= 1 and one_in(4): #If we are right next to the player, we are more likely to notice
			return True
		if not one_in(6): #Only make the check every 6 turns on average
			return False
		pen = max(dist - 2, 0) #Distance penalty; it's harder to guess the position of an invisible player who's far away
		if not player.last_moved:
			pen += 5 #If the player doesn't move, it's harder to know where they are
		return dice(1, 20) + div_rand(self.WIS - 10, 2) - pen >= dice(1, 20) + div_rand(player.DEX - 10, 2)
		
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
				
	def reset_track_timer(self):
		self.track_timer = random.randint(25, 65)
				
	def on_alerted(self, target=None):
		player = self.g.player
		self.is_aware = True
		if target is not None and target is not playet:
			self.target = None
		self.last_seen = (player.x, player.y)
		self.reset_track_timer()
				
	def stop_tracking(self):
		self.last_seen = None
		self.track_timer = 0
		self.is_aware = False
		self.dir = None
		self.target = None
		
	def apply_armor(self, dam, armor_div=1):
		prot = random.randint(0, 2*self.armor)
		prot = div_rand(prot, armor_div)
		return max(0, dam - prot)
		
	def has_line_of_fire(self):
		player = self.g.player
		return self.g.board.is_clear_path((self.x, self.y), (player.x, player.y))
		
	def sees_target(self):
		if self.target is self.g.player:
			return self.sees_player()
		if not self.target:
			return False
		target = self.target
		if self.g.board.line_of_sight((self.x, self.y), (target.x, target.y)):
			return True
		return self.g.board.line_of_sight((target.x, target.y), (self.x, self.y))
	
	def actions(self):
		if self.has_effect("Asleep") or self.has_effect("Stunned") or self.has_effect("Paralyzed"):
			self.energy = 0
			return
		if self.target is None:
			self.target = self.g.player
		if self.is_friendly():
			self.is_aware = True
		mon_typ = self.__class__.__name__
		if mon_typ == "Troll" and self.HP < self.MAX_HP:
			regen = 2 + one_in(3)
			self.HP = min(self.MAX_HP, self.HP + regen)
			if one_in(2 + self.distance(self.g.player)//2):
				self.g.print_msg_if_sees((self.x, self.y), f"The {self.name} slowly regenerates.")
		board = self.g.board
		player = self.g.player
		target = self.target
		confused = self.has_effect("Confused") and not one_in(4)
		guessplayer = False
		if self.is_aware and player.has_effect("Invisible"):
			guessplayer = self.can_guess_invis() #Even if the player is invisible, the monster may still be able to guess their position
		if confused:
			dirs = [(-1, 0), (1, 0), (0, 1), (0, -1)]
			if not self.move(*random.choice(dirs)): #Only try twice
				if not self.move(*(d := random.choice(dirs))):
					x, y = self.x + d[0], self.y + d[1]
					obstacle = ""
					if board.blocks_sight(x, y):
						obstacle = "wall"
					elif (m := self.g.get_monster(x, y)):
						obstacle = m.name
					if obstacle:
						self.g.print_msg_if_sees((self.x, self.y), f"The {self.name} bumps into the {obstacle}.")
					self.energy -= div_rand(self.get_speed(), 2) #We bumped into something while confused
			self.energy = min(self.energy, 0)
		elif not self.is_friendly() and self.has_effect("Frightened"):
			if self.sees_player():
				dirs = [(-1, 0), (1, 0), (0, 1), (0, -1)]
				random.shuffle(dirs)
				dist = self.distance(player)
				if dist <= 1 and one_in(4): #If we are already next to the player when frightened, there's a small chance we try to attack before running away
					self.energy -= self.get_speed()
					self.do_melee_attack()
				else:
					for dx, dy in dirs:
						newx, newy = self.x + dx, self.y + dy	
						newdist = abs(newx - player.x) + abs(newy - player.y)
						if newdist >= dist: #Don't move closer to the player
							self.move(dx, dy)
							break
					else:
						if x_in_y(2, 5): #If we are frightened and nowhere to run, try attacking
							if dist <= 1:
								self.energy -= self.get_speed()
								self.do_melee_attack()
							elif self.ranged and target is player and self.should_use_ranged():
								self.do_ranged_attack()
			elif one_in(2) and dice(1, 20) + calc_mod(self.WIS) >= 15:
				self.lose_effect("Frightened")
		elif self.is_friendly():
			can_see = (self.x, self.y) in player.fov
			if can_see and (mons := list(player.monsters_in_fov())):
				dist = 999
				closest = None
				for m in mons:
					if not board.is_clear_path((self.x, self.y), (m.x, m.y)):
						if not board.is_clear_path((m.x, m.y), (self.x, self.y)):
							continue
					if (d := self.distance(m)) < dist:
						dist = d
						closest = m
				if dist <= 1:
					self.melee_attack(m)
				else:
					self.path_towards(m.x, m.y)	
			if self.distance(player) > 4 or not can_see:
				self.path_towards(player.x, player.y)
			elif one_in(6):
				dirs = [(-1, 0), (1, 0), (0, 1), (0, -1)]
				random.shuffle(dirs)
				for d in dirs:
					if self.move(*d):
						self.dir = d
						break
		elif (self.is_aware or (target is not player and self.sees_target())) and (self.sees_player() or guessplayer):
			xdist = target.x - self.x
			ydist = target.y - self.y
			self.last_seen = (target.x, target.y)
			self.reset_track_timer()
			if self.distance(target) <= 1:
				self.energy -= self.get_speed()
				self.do_melee_attack(target)
			elif self.ranged and target is player and self.should_use_ranged():
				self.do_ranged_attack()
			else:
				dx = 1 if xdist > 0 else (-1 if xdist < 0 else 0)
				dy = 1 if ydist > 0 else (-1 if ydist < 0 else 0)
				axdist = abs(xdist)
				aydist = abs(ydist)
				old = self.energy
				if axdist > aydist or (axdist == aydist and one_in(2)):
					maintains = target is not player or (self.x + dx, self.y) in player.fov #Choose a direction that doesn't break line of sight
					if not (maintains and dx != 0 and self.move(dx, 0)) and dy != 0:
						self.move(0, dy)
				else:
					maintains = target is not player or (self.x, self.y + dy) in player.fov
					if not (maintains and dy != 0 and self.move(0, dy)) and dx != 0:
						self.move(dx, 0)
				moved = self.energy < old
				if not moved and self.distance(target) <= 4 and one_in(5):
					could_route_around = self.g.monster_at(self.x+dx, self.y) or self.g.monster_at(self.x, self.y+dy)
					if could_route_around:
						self.path_towards(*self.last_seen, maxlen=self.distance(target)+3)
		else:
			if self.target is not player: #We lost sight of a target; go back to targeting the player
				self.target = player
			target = self.target
			if target.has_effect("Invisible") and (self.x, self.y) == self.last_seen:
				self.guess_rand_invis() 
			if self.target is player and self.last_seen:
				if self.track_timer > 0:
					if player.has_effect("Invisible"):
						check = dice(1, 20) + calc_mod(player.DEX) < 10 + calc_mod(self.WIS)
					else:
						check = True
					self.path_towards(*self.last_seen)
					if (self.x, self.y) == self.last_seen and check:
						sees_you = self.sees_player()
						#If we reach the target position and still don't see the player, roll a stealth check to continue tracking the player
						if sees_you or dice(1, 20) + calc_mod(player.DEX) < 14 + calc_mod(self.WIS):
							self.last_seen = (player.x, player.y)
						else:
							self.stop_tracking()
				else:
					self.stop_tracking()
			elif not one_in(5):
				choose_new = self.dir is None or (one_in(3) or not self.move(*self.dir))
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
#(A lot of these are based on DnD monsters)							
class Bat(Monster):
	min_level = 1
	diff = 1
	AC = 12
	WIS = 12
	symbol = "w"
	attacks = [
		Attack((1, 3), 0, "The {0} bites {1}")
	]	
	
	def __init__(self, g):
		#name, HP, ranged, ranged_dam
		#ranged == None means there is a chance of it using a ranged attack
		super().__init__(g, "bat", 3, False)


class Lizard(Monster):
	min_level = 1
	diff = 1
	speed = 20
	passive_perc = 9
	WIS = 8
	symbol = "r"
	attacks = [
		Attack((1, 3), 0, "The {0} bites {1}")
	]
	
	def __init__(self, g):
		super().__init__(g, "lizard", 4, False)
				
class Kobold(Monster):
	diff = 2
	min_level = 3
	AC = 12
	WIS = 7
	to_hit = 4
	passive_perc = 8
	beast = False
	symbol = "K"
	weapon = Dagger
	attacks = [
		Attack((2, 4), 4, "The {0} hits {1} with its dagger")
	]
		
	def __init__(self, g):
		super().__init__(g, "kobold", 10, None, (2, 4))

class ClawGrapple(Attack):
	
	def __init__(self, dmg, to_hit):
		super().__init__(dmg, to_hit, "The {0} claws {1}")
		
	def on_hit(self, player, mon, dmg):
		if not one_in(3) and player.add_grapple(mon):
			player.g.print_msg(f"The {mon.name} grapples you with its claw!", "red")

class CrabClaw(ClawGrapple):
	
	def __init__(self):
		super().__init__((2, 6), 3)
			
class GiantCrab(Monster):
	diff = 3
	min_level = 4
	AC = 12
	WIS = 9
	to_hit = 3
	armor = 2	
	passive_perc = 9
	symbol = "C"
	attacks = [
		CrabClaw()
	]
	
	def __init__(self, g):
		super().__init__(g, "giant crab", 20, False)	
						
class GiantRat(Monster):
	diff = 2
	min_level = 5
	AC = 12
	to_hit = 4
	passive_perc = 10
	symbol = "R"
	attacks = [
		Attack((2, 4), 4, "The {0} bites {1}")
	]
	
	def __init__(self, g):
		super().__init__(g, "giant rat", 14, False)


class PoisonBite(Attack):
	
	def __init__(self):
		super().__init__((2, 4), 6, "The {0} bites {1}")
	
	def on_hit(self, player, mon, dmg):
		g = player.g
		poison = dice(4, 6) + dice(1, 3)
		if dmg < poison:
			poison = random.randint(dmg, poison)
		player.do_poison(poison)			

class GiantPoisonousSnake(Monster):
	diff = 3
	min_level = 8
	AC = 14
	WIS = 10
	to_hit = 6
	passive_perc = 10
	symbol = "S"
	attacks = [
		PoisonBite()
	]
		
	def __init__(self, g):
		super().__init__(g, "giant poisonous snake", 22, False)

class Skeleton(Monster):
	diff = 3
	min_level = 7
	AC = 12
	WIS = 8
	to_hit = 4
	armor = 1
	passive_perc = 9
	beast = False
	symbol = "F"
	weapon = Shortsword
	attacks = [
		Attack((2, 6), 4, "The {0} hits you with its shortsword")
	]
		
	def __init__(self, g):
		super().__init__(g, "skeleton", 26, None, (2, 6))

class GiantBat(Monster):
	diff = 3
	speed = 60
	min_level = 8
	AC = 13
	WIS = 12
	to_hit = 4
	symbol = "W"
	attacks = [
		Attack((2, 6), 4, "The {0} bites {1}")
	]

	def __init__(self, g):
		super().__init__(g, "giant bat", 26, False)

class GiantLizard(Monster):
	diff = 3
	min_level = 9
	AC = 12
	to_hit = 4
	passive_perc = 10
	symbol = "L"
	attacks = [
		Attack((2, 8), 4, "The {0} bites {1}")
	]
	
	def __init__(self, g):
		super().__init__(g, "giant lizard", 38, False)

class GiantGoat(Monster):
	diff = 4
	speed = 40
	min_level = 12
	AC = 11
	WIS = 12
	to_hit = 5
	symbol = "G"
	attacks = [
		Attack((4, 4), 4, "The {0} rams {1}")
	]
		
	def __init__(self, g):
		super().__init__(g, "giant goat", 38, False)

class Orc(Monster):
	diff = 4
	speed = 30
	min_level = 12
	AC = 11
	WIS = 11
	to_hit = 5
	armor = 2
	passive_perc = 10
	beast = False
	symbol = "O"
	weapon = Greataxe
	attacks = [
		Attack((2, 12), 3, "The {0} hits {1} with its greataxe")
	]
		
	def __init__(self, g):
		super().__init__(g, "orc", 30, None, (2, 6))

class BlackBear(Monster):
	diff = 4
	speed = 40
	min_level = 13
	AC = 11
	WIS = 12
	to_hit = 3
	armor = 1
	passive_perc = 13
	symbol = "B"
	attacks = [
		Attack((2, 6), 3, "The {0} bites {1}"),
		Attack((4, 4), 3, "The {0} claws {1}")
	]
		
	def __init__(self, g):
		super().__init__(g, "black bear", 38, False)

class BrownBear(Monster):
	diff = 5
	speed = 40
	min_level = 15
	AC = 10
	WIS = 12
	to_hit = 3
	armor = 1
	passive_perc = 13
	symbol = "&"
	attacks = [
		Attack((2, 8), 3, "The {0} bites {1}"),
		Attack((4, 6), 3, "The {0} claws {1}")
	]
		
	def __init__(self, g):
		super().__init__(g, "brown bear", 68, False)

class GiantEagle(Monster):
	diff = 5
	AC = 13
	WIS = 12
	min_level = 16
	to_hit = 5
	passive_perc = 14
	symbol = "E"
	attacks = [
		Attack((2, 6), 5, "The {0} attacks {1} with its beak"),
		Attack((4, 6), 5, "The {0} attacks {1} with its talons")
	]
		
	def __init__(self, g):
		super().__init__(g, "giant eagle", 52, False)

class Ogre(Monster):
	diff = 6
	AC = 9
	WIS = 7
	min_level = 20
	to_hit = 6
	armor = 2
	passive_perc = 8
	beast = False
	symbol = "J"
	weapon = Club
	attacks = [
		Attack((2, 6), 6, "The {0} hits {1} with its club"),
	]
		
	def __init__(self, g):
		super().__init__(g, "ogre", 118, False)

class PolarBear(Monster):
	diff = 6
	speed = 40
	min_level = 18
	AC = 10
	WIS = 13
	to_hit = 7
	armor = 2
	passive_perc = 13
	symbol = "P"
	attacks = [
		Attack((2, 8), 7, "The {0} bites {1}"),
		Attack((4, 6), 7, "The {0} claws {1}")
	]
		
	def __init__(self, g):
		super().__init__(g, "polar bear", 84, False)

class Rhinoceros(Monster):
	diff = 6
	speed = 40
	min_level = 19
	AC = 9
	WIS = 12
	to_hit = 7
	armor = 2
	passive_perc = 13
	symbol = "Y"
	attacks = [
		Attack((2, 8), 7, "The {0} gores {1}")
	]
		
	def __init__(self, g):
		super().__init__(g, "rhinoceros", 90, False)

class WightLifeDrain(Attack):
	
	def __init__(self):
		super().__init__((2, 6), 4, "The {0} uses life drain")
	
	def on_hit(self, player, mon, dmg):
		g = player.g
		g.print_msg("Your life force is drained!", "red")
		player.drain(random.randint(1, dmg))

class Wight(Monster):
	diff = 7
	speed = 30
	min_level = 21
	AC = 12
	WIS = 13
	to_hit = 4
	armor = 2
	passive_perc = 13
	symbol = "T"
	weapon = Longsword
	attacks = [
		Attack((2, 8), 7, "The {0} hits {1} with its longsword"),
		[
			Attack((2, 8), 7, "The {0} hits {1} with its longsword"),
			WightLifeDrain()
		]
	]
		
	def __init__(self, g):
		super().__init__(g, "wight", 90, False)

class Sasquatch(Monster):
	diff = 7
	speed = 40
	min_level = 22
	AC = 10
	WIS = 16
	to_hit = 6
	armor = 2
	passive_perc = 17
	beast = False
	symbol = "Q"
	attacks = [
		Attack((2, 8), 6, "The {0} punches {1} with its fist"),
		Attack((2, 8), 6, "The {0} punches {1} with its fist")
	]
		
	def __init__(self, g):
		super().__init__(g, "sasquatch", "Q", 118, False)

class ScorpionClaw(ClawGrapple):
	
	def __init__(self):
		super().__init__((2, 8), 4)
		
class ScorpionSting(Attack):
	
	def __init__(self):
		super().__init__((2, 10), 4, "The {0} stings {1}")
	
	def on_hit(self, player, mon, dmg):
		g = player.g
		poison = dice(4, 10)
		if dmg < poison:
			poison = random.randint(dmg, poison)
		player.do_poison(poison)			
		
class GiantScorpion(Monster):
	diff = 7
	speed = 40
	min_level = 21
	AC = 15
	WIS = 9
	to_hit = 4
	passive_perc = 9
	grapple_dc = 12
	symbol = "D"
	attacks = [
		ScorpionClaw(),
		ScorpionClaw(),
		ScorpionSting()
	]
		
	def __init__(self, g):
		super().__init__(g, "giant scorpion", 98, False)

class AdhesiveSlimeAttack(Attack):
	
	def __init__(self):
		super().__init__((6, 8), 6, "The {0} attacks {1}")
	
	def on_hit(self, player, mon, dmg):
		g = player.g
		if not one_in(7) and player.add_grapple(mon):
			g.print_msg(f"The {mon.name}'s pseudopod adheres to you, holding you in place!", "red")

class GiantGreenSlime(Monster):
	diff = 8
	speed = 30
	min_level = 24
	AC = 12
	WIS = 8
	to_hit = 4
	passive_perc = 9
	grapple_dc = 19 #It's so sticky that the escape DC is set quite high
	symbol = "M"
	attacks = [
		AdhesiveSlimeAttack(),
	]
		
	def __init__(self, g):
		super().__init__(g, "giant green slime", 168, False)

class Ettin(Monster):
	diff = 8
	speed = 40
	min_level = 26
	AC = 9
	WIS = 10
	to_hit = 7
	passive_perc = 14
	armor = 4
	symbol = "Ň"
	weapon = [Battleaxe, Morningstar]
	attacks = [
		Attack((4, 9), 7, "The {0} attacks {1} with a battleaxe"),
		Attack((4, 9), 7, "The {0} attacks {1} with a morningstar"),
	]
		
	def __init__(self, g):
		super().__init__(g, "ettin", 170, False)

class RubberPseudopod(Attack):
	
	def __init__(self):
		super().__init__((6, 9), 7, "The {0} hits {1} with its pseudopod")

	def on_hit(self, player, mon, dmg):
		g = player.g
		if mon.distance(player) <= 1 and one_in(2) and dice(1, 20) + calc_mod(player.DEX) < 14:
			dx = player.x - mon.x
			dy = player.y - mon.y
			if dx != 0:
				dx //= abs(dx)
			if dy != 0:
				dy //= abs(dy)
			dx *= 2
			dy *= 2
			player.knockback(dx, dy)
			
class RubberSlime(Monster):
	diff = 9
	speed = 30
	min_level = 29
	AC = 9
	WIS = 10
	to_hit = 7
	passive_perc = 10
	symbol = "U"
	attacks = [
		RubberPseudopod()
	]
	
	rubbery = True #It shrugs off most bludgeoning damage
		
	def __init__(self, g):
		super().__init__(g, "rubbery slime", 170, False)
