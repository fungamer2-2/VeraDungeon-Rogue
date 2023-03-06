import random, time
from utils import *

class Item:
	description = "This is a generic item that does nothing special. You shouldn't see this in-game."
	
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
		MAX_HP = player.get_max_hp()
		if player.HP >= MAX_HP:
			g.print_msg("Your HP is already full!")
			return False
		else:	
			recover = 10 + dice(2, 40)
			g.print_msg("You recover some HP.")
			player.HP = min(MAX_HP, player.HP + recover)
			return True
			
class SpeedPotion(Item):
	description = "Consuming this potion temporarily speeds the movement of the one who drinks it. However, once the effect wears off, they will feel lethargic for a short period."
	
	def __init__(self):
		super().__init__("speed potion", "S")
		
	def use(self, player):
		g = player.g
		g.print_msg("You drink a speed potion.")
		player.lose_effect("Lethargy", silent=True)
		if player.has_effect("Haste"):
			g.print_msg("Your speed begins to last even longer.")
		player.gain_effect("Haste", random.randint(40, 60))
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
		player.gain_effect("Invisible", random.randint(45, 70))
		return True
		
class RejuvPotion(Item):
	description = "Consuming this potion significantly improves regeneration for a short duration."
	
	def __init__(self):
		super().__init__("potion of rejuvenation", "J")
		
	def use(self, player):
		g = player.g
		g.print_msg("You drink a potion of rejuvenation.")
		if player.has_effect("Rejuvenated"):
			player.lose_effect("Rejuvenated", silent=True) #This doesn't stack
		g.print_msg("You drink a potion of rejuvenation.")
		player.gain_effect("Rejuvenated", random.randint(20, 25))
		return True
		
class ClairPotion(Item):
	description = "Consuming this potion allows you to see beyond ehat you can normally see."
	
	def __init__(self):
		super().__init__("potion of clairvoyance", "Y")
		
	def use(self, player):
		g = player.g
		g.print_msg("You drink a clairvoyance potion.")
		if player.has_effect("Clairvoyance"):
			g.print_msg("You feel even more clairvoyant.")
		player.gain_effect("Clairvoyance", random.randint(45, 90))
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
				m.reset_check_timer()
				m.is_aware = False
		else:
			g.print_msg("Nothing seems to happen.")
		return True
		
class StunScroll(Scroll):
	description = "Reading this scroll stuns a random amount of nearby monsters."
	
	def __init__(self):
		super().__init__("scroll of stun")
	
	def use(self, player):
		g = player.g
		g.print_msg("You read a scroll of stun. The scroll crumbles to dust.")
		seen = list(player.monsters_in_fov())
		random.shuffle(seen)
		affects = seen[:random.randint(1, len(seen))]
		for m in affects:
			if m.HP <= random.randint(125, 175):
				g.print_msg(f"The {m.name} is stunned!")
				m.gain_effect("Stunned", random.randint(6, 22))
			else:
				g.print_msg(f"The {m.name} is unaffected.")
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
		
class SummonScroll(Scroll):
	description = "Reading this scroll will summon friendly creatures."
	
	def __init__(self):
		super().__init__("scroll of summoning")
	
	def use(self, player):
		g = player.g
		g.print_msg("You read a scroll of summoning. The scroll crumbles to dust.")

		points = list(player.fov)
		points.remove((player.x, player.y))
		types = list(filter(lambda t: t.diff <= 8 and g.level >= t.min_level, g.mon_types))
		num = random.randint(2, 3)
		random.shuffle(points)
		points.sort(key=lambda p: abs(p[0] - player.x) + abs(p[1] - player.y))
		ind = 0
		while ind < len(points) and num > 0:
			typ = random.choice(types)
			duration = random.randint(50, 80)
			pos = points[ind]
			if g.monster_at(*pos):
				ind += 1
				continue
			m = typ(g)
			m.ranged = False
			m.place_at(*pos)
			m.summon_timer = duration
			g.monsters.append(m)
			ind += random.randint(1, 2)
			num -= 1
		return True
		
		
class Activity:
	
	def __init__(self, name, time):
		self.name = name
		self.time = time
		
	def on_finished(self, player):
		pass
		
class WearArmor(Activity):
	
	def __init__(self, armor):
		super().__init__(f"putting on your {armor.name}", 30)
		self.armor = armor
		
	def on_finished(self, player):
		player.armor = self.armor
		g = player.g
		g.print_msg(f"You finish putting on your {self.armor.name}.")
		
class RemArmor(Activity):
	
	def __init__(self, armor):
		super().__init__(f"removing your {armor.name}", 20)
		self.armor = armor
		
	def on_finished(self, player):
		player.armor = None
		g = player.g
		g.print_msg(f"You finish removing your {self.armor.name}.")
				
class Armor(Item):
	description = "This is armor. It may protect you from attacks."
	stealth_pen = 0
	dex_mod_softcap = None #This represents the softcap for dexterity bonus to AC
	
	def __init__(self, name, symbol, protect):
		super().__init__(name, symbol)
		self.protect = protect
		
	def use(self, player):
		g = player.g
		if player.armor and player.armor.name == self.name:
			if g.yes_no(f"Take off your {self.name}?"):
				player.activity = RemArmor(self)
		else:
			g.print_msg(f"You begin putting on your {self.name}.")
			player.activity = WearArmor(self)
		return False #Do not remove armor from inventory

class LeatherArmor(Armor):
				
	def __init__(self):
		super().__init__("leather armor", "L", 1)

class HideArmor(Armor):
				
	def __init__(self):
		super().__init__("hide armor", "H", 2)
		
class ChainShirt(Armor):
	dex_mod_softcap = 4
				
	def __init__(self):
		super().__init__("chain shirt", "C", 3)

class ScaleMail(Armor):
	stealth_pen = 2
	dex_mod_softcap = 3
				
	def __init__(self):
		super().__init__("scale mail", "M", 4)

class HalfPlate(Armor):
	stealth_pen = 4
	dex_mod_softcap = 2
				
	def __init__(self):
		super().__init__("half-plate", "A", 5)

class ChainMail(Armor):
	stealth_pen = 6
	dex_mod_softcap = 1
				
	def __init__(self):
		super().__init__("chainmail", "I", 6)

class SplintArmor(Armor):
	stealth_pen = 8
	dex_mod_softcap = 0
				
	def __init__(self):
		super().__init__("splint armor", "S", 7)

class PlateArmor(Armor):
	stealth_pen = 10
	dex_mod_softcap = -1
				
	def __init__(self):
		super().__init__("plate armor", "T", 8)
		
class Weapon(Item):
	description = "This is a weapon that can be used to attack enemies."
	crit_mult = 2
	crit_thresh = 20
	dmg_type = "default"
	
	def __init__(self, name, symbol, dmg, finesse=False, heavy=False, thrown=None):
		super().__init__(name, symbol)
		self.dmg = dmg
		self.finesse = finesse
		self.heavy = heavy #Heavy weapons get a -2 penalty on attack rolls
		self.thrown = thrown #Either None or a 2-tuple representing short and long range
		
	def use(self, player):
		g = player.g
		if self is player.weapon:
			if g.yes_no(f"Put away your {self.name}?"):
				player.weapon = UNARMED
				player.energy -= player.get_speed()
			else:
				return False
		else:
			if player.weapon is not UNARMED:
				player.energy -= player.get_speed()
				g.print_msg(f"You switch to your {self.name}.")
			else:
				g.print_msg(f"You wield a {self.name}.")
			player.weapon = self
			
	def roll_dmg(self):
		return dice(*self.dmg)
		
	def on_hit(self, player, mon):
		pass
		
class NullWeapon(Weapon):
	description = "You are punching with your fists. You shouldn't see this in-game."
	dmg_type = "bludgeon"
	
	def __init__(self):
		super().__init__("unarmed", "f", (1, 2))
		
UNARMED = NullWeapon()

class Club(Weapon):
	dmg_type = "bludgeon"
	
	def __init__(self):
		super().__init__("club", "!", (1, 4))
		
class Dagger(Weapon):
	crit_thresh = 19
	dmg_type = "pierce"
	
	def __init__(self):
		super().__init__("dagger", "/", (1, 4), finesse=True, thrown=(4, 12))

class Handaxe(Weapon):
	crit_mult = 3
	dmg_type = "slash"
	
	def __init__(self):
		super().__init__("handaxe", "h", (1, 6), thrown=(4, 12))

class Javelin(Weapon):
	dmg_type = "bludgeon"
	
	def __init__(self):
		super().__init__("javelin", "j", (1, 6), thrown=(6, 24))

class Mace(Weapon):
	dmg_type = "bludgeon"
	
	def __init__(self):
		super().__init__("mace", "T", (1, 6))

class Shortsword(Weapon):
	crit_thresh = 19
	dmg_type = "slash"
	
	def __init__(self):
		super().__init__("shortsword", "i", (1, 6), finesse=True)

class Longsword(Weapon):
	crit_thresh = 19
	dmg_type = "slash"
	
	def __init__(self):
		super().__init__("longsword", "I", (1, 9))

class Greatclub(Weapon):
	dmg_type = "bludgeon"
	
	def __init__(self):
		super().__init__("greatclub", "P", (1, 8))

class Battleaxe(Weapon):
	crit_mult = 3
	dmg_type = "slash"
	
	def __init__(self):
		super().__init__("battleaxe", "F", (1, 9))

class Morningstar(Weapon):
	dmg_type = "pierce"
	
	def __init__(self):
		super().__init__("morningstar", "k", (1, 8))

class Glaive(Weapon):
	dmg_type = "slash"
	
	def __init__(self):
		super().__init__("glaive", "L", (1, 10), heavy=True)
		
class Greataxe(Weapon):
	crit_mult = 3
	dmg_type = "slash"
	
	def __init__(self):
		super().__init__("greataxe", "G", (1, 12), heavy=True)

class Wand(Item):
	description = "This is a wand."
	
	def __init__(self, name, charges, efftype="blast"):
		super().__init__(name, "Î")
		self.charges = charges
		self.efftype = efftype
	
	def wand_effect(self, player, mon):
		self.g.print_msg("Nothing special seems to happen.")
		
	def use(self, player):
		g = player.g
		monsters = list(player.monsters_in_fov())
		g.print_msg(f"This wand has {self.charges} charges remaining.")
		target = g.select_monster_target()
		if not target:
			return
		if g.board.line_of_sight((player.x, player.y), (target.x, target.y)):
			line = list(g.board.line_between((player.x, player.y), (target.x, target.y)))
		else:
			line = list(g.board.line_between((target.x, target.y), (player.x, player.y)))
			line.reverse()
		if self.efftype == "ray":
			t = player.distance(target)
			def raycast(line, rnd):
				line.clear()
				dx = target.x - player.x
				dy = target.y - player.y
				i = 1
				x, y = player.x, player.y
				hittarget = False
				while True:
					nx = rnd(player.x + dx * (i/t))
					ny = rnd(player.y + dy * (i/t))
					i += 1
					if (nx, ny) == (x, y):
						continue
					if (x, y) == (target.x, target.y):
						hittarget = True
					if g.board.blocks_sight(nx, ny):
						return hittarget #The ray should at least hit the target if it doesn't reach anyone else
					x, y = nx, ny
					line.append((x, y))
			rounds = (int, round, math.ceil) #Try different rounding functions, to ensure that the ray passes through at least the target
			line = []
			for f in rounds:
				if raycast(line, f):
					break
			g.blast.clear()
			for x, y in line:
				t = g.get_monster(x, y)
				if t is not None:
					if not target.despawn_summon():
						self.wand_effect(player, t)
						t.on_alerted()
				g.blast.add((x, y))
				g.draw_board()
				time.sleep(0.001)
			time.sleep(0.05)
			g.blast.clear()
			g.draw_board()
		else:
			for x, y in line:
				g.set_projectile_pos(x, y)
				g.draw_board()
				time.sleep(0.03)
				if (t := g.get_monster(x, y)) is not None:
					if t is not target and x_in_y(3, 5): #If a creature is in the way, we may hit it instead of our intended target.
						g.print_msg(f"The {t.name} is in the way.")
						target = t
						break
			g.clear_projectile()
			if not target.despawn_summon():
				self.wand_effect(player, target)
		self.charges -= 1
		player.did_attack = True
		alert = 2 + (self.efftype == "ray") #Ray effects that affect all monsters in a line are much more likely to alert monsters
		for m in player.monsters_in_fov():
			if x_in_y(alert, 4) or m is target: #Zapping a wand is very likely to alert nearby monsters to your position
				m.on_alerted()
		return (True if self.charges <= 0 else None)
		
class MagicMissile(Wand):
	description = "This wand can be used to fire magic missiles at creatures, which will always hit."
	
	def __init__(self):
		super().__init__("wand of magic missiles", random.randint(3, 7))
	
	def wand_effect(self, player, target):
		g = player.g
		dam = 0
		for _ in range(3):
			dam += target.apply_armor(random.randint(2, 5))
		msg = f"The magic missiles hit the {target.name} "
		if dam <= 0:
			msg += "but do no damage."
		else:
			target.HP -= dam
			msg += f"for {dam} damage."
			if target.HP > 0:
				msg += f" Its HP: {target.HP}/{target.MAX_HP}"
		g.print_msg(msg)
		if target.HP <= 0:
			player.defeated_monster(target)

class PolymorphWand(Wand):
	description = "This wand can be used to polymorph nearby enemies into something weaker."
	
	def __init__(self):
		super().__init__("polymorph wand", random.randint(random.randint(2, 7), 7))
	
	def wand_effect(self, player, target):
		g = player.g
		if dice(1, 20) + calc_mod(target.WIS) >= 15:
			g.print_msg(f"The {target.name} resists.")
		else:
			target.polymorph()
			
class WandOfFear(Wand):
	description = "This wand can be used to make nearby enemies frightened of the player."
	
	def __init__(self):
		super().__init__("wand of fear", random.randint(3, 7))
	
	def wand_effect(self, player, target):
		g = player.g
		if dice(1, 20) + calc_mod(target.WIS) >= 15:
			g.print_msg(f"The {target.name} resists.")
		else:
			g.print_msg(f"The {target.name} is frightened!")
			target.gain_effect("Frightened", random.randint(30, 60))
	
class LightningWand(Wand):
	description = "This wand can be used to cast lightning bolts, dealing damage to nearby enemies."
	
	def __init__(self):
		super().__init__("wand of lightning", random.randint(3, 7), efftype="ray")
	
	def wand_effect(self, player, target):
		g = player.g
		val = calc_mod(2 * (target.AC - 10) + 10)
		numdice = 8
		if not target.has_effect("Paralyzed") and dice(1, 20) + val >= 15:
			numdice = 4
			g.print_msg(f"The {target.name} partially resists.")
		damage = target.apply_armor(dice(numdice, 6))
		msg = f"The bolt strikes the {target.name} "
		if damage <= 0:
			msg += "but does no damage."
		else:
			msg += f"for {damage} damage."
			target.HP -= damage
		g.print_msg(msg)
		if target.HP <= 0:
			player.defeated_monster(target)

class Ring(Item):
	description = "This is a ring that can provide a passive bonus when equipped."
	#Passives can be: STR, DEX, protect, stealth, dodge, to_hit
	_valid_passives = {"STR", "DEX", "protect", "stealth", "dodge", "to_hit"}
	def __init__(self, name, wear_msg, rem_msg, passives={}):
		super().__init__(name, "ô")
		for key in passives:
			if key not in self._valid_passives:
				raise ValueError(f"{key!r} is not a valid passive")
		self.wear_msg = wear_msg
		self.rem_msg = rem_msg
		self.passives = passives
		
	def use(self, player):
		g = player.g
		worn_rings = player.worn_rings
		if self in worn_rings:
			if g.yes_no(f"Take off your {self.name}?"):
				g.print_msg(f"You take off your {self.name}.")
				g.print_msg(self.rem_msg)
				worn_rings.remove(self)
				player.recalc_passives()
		else:
			if len(worn_rings) >= 7:
				g.print_msg(f"You're already wearing the maximum number of rings.")
				return False	
			else:
				g.print_msg(f"You put on a {self.name}.")
				g.print_msg(self.wear_msg)
				worn_rings.append(self)
				player.recalc_passives()
				
class ProtectionRing(Ring):
	description = "This ring can provide a slight bonus to protection when equipped."
	
	def __init__(self):
		super().__init__("ring of protection", "You feel more protected.", "You feel more vulnerable.",
			passives={"protect": 1}
		)
		
class StrengthRing(Ring):
	description = "This ring can provide a bonus to strength when equipped."
	
	def __init__(self):
		super().__init__("ring of strength", "You feel stronger.", "You don't feel as strong anymore.",
			passives={"STR": 3}
		)

class DexterityRing(Ring):
	description = "This ring can provide a bonus to dexterity when equipped."
	
	def __init__(self):
		super().__init__("ring of dexterity", "You feel like your agility has improved.", "You feel less agile.",
			passives={"DEX": 3}
		)		