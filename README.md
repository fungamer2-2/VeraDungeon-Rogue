# Roguelike
My roguelike game in Python

(Note: This is currently a work in progress)

To play the game, all you need is a Python 3 Interpreter
(Due to use of walrus operators, this doesn't work for Python versions below 3.8, however this game has only been tested on Python 3.9)

### Controls<br />
`wasd` keys to move around
`q` and `z` keys to scroll the message log<br />
`f` - view info of monster types in view<br />
`u` - use an item from inventory (just type in the name of the item)<br />
`r` - rest until HP full<br />
`p` - pick up an item

### Gameplay
Your goal is to fight the monsters in a randomly generated dungeon. Move into a monster to attack. <br />
Monsters will start off unaware of you, but depending on the result of a stealth check, there is a chance they will notice you. <br />
Monsters who don't yet notice you will have a white background. If you manage to attack an unaware monster, you will be able to make a sneak attack to deal bonus damage.
There are also various potions that you can use to help you. <br />
There is no end goal at the moment, right now, it's just "see how long you can survive." I may consider eventually adding an end goal in the future.
