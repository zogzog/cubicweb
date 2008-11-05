class Company(EntityType):
    name = String()

class Division(Company):
    __specializes_schema__ = True

class SubDivision(Division):
    __specializes_schema__ = True

