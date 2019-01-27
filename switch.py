class Switch: 
    def __init__(self, identity):
        self.identity = identity
        self.previous = ""
        self.links = list()
        self.distance = 0

    def add_link(self, switch_link):
        if type(switch_link) == Link:
            self.links.append(switch_link)
        else:
            raise TypeError("Incorrect type for neighbour")

    def __lt__(self, other):
        return self.distance < other.distance

switch = Switch("a")
switch_list = [switch]
switch_set = {switch}
switch_list[0].distance = 100
item = switch_set.pop()
print(item.distance)