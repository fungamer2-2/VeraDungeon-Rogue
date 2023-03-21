import random

class Effect:
	name = "Generic Effect"
	
	def __init__(self, duration, add_msg, rem_msg):
		self.duration = duration
		self.add_msg = add_msg
		self.rem_msg = rem_msg
		
	def on_expire(self, player):
		pass
		
class Lethargy(Effect):
	name = "Lethargy"
	
	def __init__(self, duration):
		super().__init__(duration, "You begin to feel lethargic.", "Your energy returns.")
				
class Haste(Effect):
	name = "Haste"
	
	def __init__(self, duration):
		super().__init__(duration, "You begin to move faster.", "Your extra speed runs out.")
	
	def on_expire(self, player):
		g = player.g
		player.gain_effect("Lethargy", random.randint(4, 10))
		
class Resistance(Effect):
	name = "Resistance"
	
	def __init__(self, duration):
		super().__init__(duration, "You feel more resistant to damage.", "You feel vulnerable again.")
	
class Invisible(Effect):
	name = "Invisible"
	
	def __init__(self, duration):
		super().__init__(duration, "You become invisible.", "You become visible again.")

class Rejuvenated(Effect):
	name = "Rejuvenated"
	
	def __init__(self, duration):
		super().__init__(duration, "You begin to feel extremely rejuvenated.", "The rejuvenation wears off.")

class Clairvoyance(Effect):
	name = "Clairvoyance"
	
	def __init__(self, duration):
		super().__init__(duration, "You feel much more perceptive.", "Your clairvoyance fades.")

class Confused(Effect):
	name = "Confused"
	
	def __init__(self, duration):
		super().__init__(duration, "You feel confused.", "You are no longer confused.")
