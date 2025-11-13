# Import admin configurations from each folder
# This will automatically register all models with the Django admin

# Import each admin module to ensure all models are registered
from .ProductFolder.admin import *
from .RawMaterialFolder.admin import *
from .PersonFolder.admin import *
from .OrderFolder.admin import *
from .AllocationFolder.admin import *
from .TransportFolder.admin import *
from .WarehouseFolder.admin import *
from .StockEntryFolder.admin import *
from .SettlementFolder.admin import *
from .RBACModel.admin import *
from .ProductionFolder.admin import *
