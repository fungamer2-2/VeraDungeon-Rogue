import random, math

def dice(num, sides):
	"Rolls a given number of dice with a given number of dice and takes the sum"
	return sum(random.randint(1, sides) for _ in range(num))

def div_rand(x, y):
	"Computes x/y then randomly rounds the result up or down depending on the remainder"
	sign = 1
	if (x > 0) ^ (y > 0):
		sign = -1
	x = abs(x)
	y = abs(y)
	mod = x % y
	return sign * (x//y + (random.randint(1, y) <= mod))

def mult_rand_frac(num, x, y):
	return div_rand(num*x, y)
	
def rand_weighted(*pairs):
	names, weights = list(zip(*pairs))
	return random.choices(names, weights=weights)[0]

def d20_prob(DC, mod, nat1=False, nat20=False):
	num_over = 21 - DC + mod
	if nat1:
		num_over = min(num_over, 19)
	if nat20:
		num_over = max(num_over, 1)
	return max(0, min(1, num_over/20))

def to_hit_prob(AC, hit_mod=0, adv=False, disadv=False):
	"""
	Calculates the percentage chance of successfully landing a hit
	adv - If true, calculates the probability with advantage
	disadv - If true, calculates the probability with disadvantage
	"""
	if adv and disadv:
		adv = False
		disadv = False
	res = d20_prob(AC, hit_mod, True, True)
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
	
def one_in(x):
	return x <= 1 or random.randint(1, x) == 1

def x_in_y(x, y):
	return random.randint(1, y) <= x	
	
def binomial(num, x, y=100):
	return sum(1 for _ in range(num) if x_in_y(x, y))
			
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
	
class Dice:
	
	def __init__(self, num, sides):
		self.num = num
		self.sides = sides
		
	def roll(self):
		return dice(num, sides)
		
	def max(self):
		return self.num*self.sides