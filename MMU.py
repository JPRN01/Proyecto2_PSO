import random
class Page:
    next_page_id = 1

    def __init__(self, logical_address, is_in_ram, physical_address=None, disk_address=None, pid=None):
        self.page_id = Page.next_page_id
        Page.next_page_id += 1
        self.logical_address = logical_address
        self.is_in_ram = is_in_ram
        self.physical_address = physical_address
        self.disk_address = disk_address
        self.pid = pid

class OPT_MMU:
    def __init__(self):
        self.real_memory = [None] * 100  # Representa la memoria real con 100 Pages
        self.virtual_memory = {}
        self.future_uses = {}  # To keep track of future uses for optimal page replacement
        self.page_reference_map = {}  # To store all future accesses for pages
        self.ptr_page_map = {}
        self.ptr_table = {}
        self.logical_page_counter = 1
        self.disk_page_counter = 1
        self.ptr_id_counter = 1
        self.clock = 0
        self.thrashing_time = 0

    def precalculate_future_uses(self, commands):
        """ Precalculate future uses for all pages based on upcoming commands """
        self.page_reference_map = {}
        future_accesses = {}
        for index, command in enumerate(commands[::-1]):  # Reverse to calculate the next use easily
            if command['type'] == 'use':
                ptr = command['ptr']
                if ptr in self.ptr_table:
                    for page_id in self.ptr_table[ptr][1]:
                        if page_id not in future_accesses:
                            future_accesses[page_id] = len(commands) - index  # Store the last future index
        self.future_uses = future_accesses

    def _optimal_page_to_replace(self):
        """ Determine which page to replace using the optimal replacement strategy """
        longest_future_use = -1
        page_to_replace_index = None
        for index, page in enumerate(self.real_memory):
            if page and page.page_id in self.future_uses:
                if self.future_uses[page.page_id] > longest_future_use:
                    longest_future_use = self.future_uses[page.page_id]
                    page_to_replace_index = index
            elif page:  # If no future use found, immediately select it for replacement
                return index
        return page_to_replace_index if page_to_replace_index is not None else 0  # Fallback

    def new(self, pid, size):
        num_pages = (size + 4095) // 4096
        ptr_id = self.ptr_id_counter
        self.ptr_id_counter += 1
        page_ids = []
        for _ in range(num_pages):
            logical_address = self.logical_page_counter
            if None not in self.real_memory:
                page_to_replace_index = self._optimal_page_to_replace()
                page_to_replace = self.real_memory[page_to_replace_index]
                # Evict page
                self._evict_page(page_to_replace_index)
                index = page_to_replace_index
            else:
                index = self.real_memory.index(None)

            is_in_ram = True
            physical_address = index
            page = self._allocate_page(logical_address, is_in_ram, physical_address, None, pid)
            page_ids.append(page.page_id)
            self.real_memory[index] = page
            self.ptr_page_map[page.page_id] = ptr_id
            self.logical_page_counter += 1

        self.ptr_table[ptr_id] = (pid, page_ids)
        return ptr_id

    def _evict_page(self, index):
        evicted_page = self.real_memory[index]
        old_ptr_id = self.ptr_page_map.get(evicted_page.page_id)
        if old_ptr_id:
            self.virtual_memory.setdefault(old_ptr_id, []).append({
                'page_id': evicted_page.page_id,
                'logical_address': evicted_page.logical_address,
                'physical_address': None,
                'disk_address': self.disk_page_counter,
                'pid': evicted_page.pid
            })
            self.disk_page_counter += 1
        self.real_memory[index] = None
        self.clock += 5  # Simulate disk access time
        self.thrashing_time += 5  # Add to thrashing time

    def _allocate_page(self, logical_address, is_in_ram, physical_address, disk_address, pid):
        return Page(logical_address, is_in_ram, physical_address, disk_address, pid)

    def use(self, ptr):
        if ptr in self.ptr_table:
            _, page_ids = self.ptr_table[ptr]
            for page_id in page_ids:
                in_memory = False
                for index, page in enumerate(self.real_memory):
                    if page and page.page_id == page_id:
                        in_memory = True
                        self.clock += 1  # Add 1s to the clock for each hit
                        # Refresh the future use data based on current state
                        self._refresh_future_uses(page_id)
                        break
                if not in_memory:
                    # Page needs to be swapped in from virtual memory
                    self._swap_page_to_ram(page_id)
        else:
            print("Ptr not found in ptr table.")

    def _swap_page_to_ram(self, page_id):
        page_to_replace_index = self._optimal_page_to_replace()
        if page_to_replace_index is not None:
            self._evict_page(page_to_replace_index)
        index = page_to_replace_index if page_to_replace_index is not None else self.real_memory.index(None)

        # Fetching page from virtual memory
        for ptr_id, pages in self.virtual_memory.items():
            for page in pages:
                if page['page_id'] == page_id:
                    pid = page.get('pid', None)
                    page_in_ram = self._allocate_page(page['logical_address'], True, index, None, pid)
                    page_in_ram.page_id = page_id  # Retain original page ID
                    self.real_memory[index] = page_in_ram
                    pages.remove(page)
                    self.ptr_page_map[page_id] = ptr_id
                    self.clock += 5  # Simulate disk access time for a swap
                    self.thrashing_time += 5  # Add to thrashing time
                    self._refresh_future_uses(page_id)
                    break

    def _refresh_future_uses(self, page_id):
        """Refresh the future use data when a page is accessed."""
        if page_id in self.future_uses:
            self.future_uses[page_id] = self.future_uses.get(page_id, float('inf')) - 1

        if self.future_uses[page_id] <= 0:
            del self.future_uses[page_id]  # Remove the page from future uses if no more references
    
    def delete(self, ptr):
        if ptr in self.ptr_table:
            _, page_ids = self.ptr_table.pop(ptr)  # Remove the ptr entry and get associated page ids
            for index, page in enumerate(self.real_memory):
                if page and page.page_id in page_ids:
                    self.real_memory[index] = None  # Free the page from real memory
                    if page.page_id in self.future_uses:
                        del self.future_uses[page.page_id]  # Remove from future uses

            # Remove pages from virtual memory
            if ptr in self.virtual_memory:
                del self.virtual_memory[ptr]  # Completely remove the ptr from virtual memory

            print(f"Deleted ptr {ptr} and its associated pages from memory.")
        else:
            print("Ptr not found in ptr table.")

    def kill(self, pid):
        to_delete = []
        # Collect all ptrs associated with this pid
        for ptr_id, (pid_val, _) in list(self.ptr_table.items()):
            if pid_val == pid:
                to_delete.append(ptr_id)

        # Delete all ptrs collected
        for ptr in to_delete:
            self.delete(ptr)

        print(f"All resources associated with PID {pid} have been successfully killed and freed.")

class MRU_MMU:
    def __init__(self):
        self.real_memory = [None] * 100  # 100 pages in real memory
        self.virtual_memory = {}
        self.mru_list = []  # List to track the most recently used pages
        self.ptr_page_map = {}
        self.ptr_table = {}
        self.logical_page_counter = 1
        self.disk_page_counter = 1
        self.ptr_id_counter = 1
        self.clock = 0
        self.thrashing_time = 0

    def new(self, pid, size):
        num_pages = (size + 4095) // 4096
        ptr_id = self.ptr_id_counter
        self.ptr_id_counter += 1
        page_ids = []
        for _ in range(num_pages):
            logical_address = self.logical_page_counter
            if None not in self.real_memory:
                mru_index = self.mru_list.pop(0)  # Remove the most recently used page
                self._evict_page(mru_index)
                index = mru_index
            else:
                index = self.real_memory.index(None)

            is_in_ram = True
            physical_address = index
            page = self._allocate_page(logical_address, is_in_ram, physical_address, None, pid)
            page_ids.append(page.page_id)
            self.real_memory[index] = page
            self.mru_list.append(index)  # Add to MRU list
            self.ptr_page_map[page.page_id] = ptr_id
            self.logical_page_counter += 1

        self.ptr_table[ptr_id] = (pid, page_ids)
        return ptr_id

    def _evict_page(self, index):
        evicted_page = self.real_memory[index]
        if evicted_page:
            old_ptr_id = self.ptr_page_map.get(evicted_page.page_id)
            if old_ptr_id:
                self.virtual_memory.setdefault(old_ptr_id, []).append({
                    'page_id': evicted_page.page_id,
                    'logical_address': evicted_page.logical_address,
                    'physical_address': None,
                    'disk_address': self.disk_page_counter,
                    'pid': evicted_page.pid
                })
                self.disk_page_counter += 1
            self.real_memory[index] = None
            self.clock += 5  # Simulate disk access time
            self.thrashing_time += 5  # Add to thrashing time

    def _allocate_page(self, logical_address, is_in_ram, physical_address, disk_address, pid):
        return Page(logical_address, is_in_ram, physical_address, disk_address, pid)

    def use(self, ptr):
        if ptr in self.ptr_table:
            _, page_ids = self.ptr_table[ptr]
            for page_id in page_ids:
                for index, page in enumerate(self.real_memory):
                    if page and page.page_id == page_id:
                        # Refresh the MRU list
                        if index in self.mru_list:
                            self.mru_list.remove(index)
                        self.mru_list.append(index)
                        self.clock += 1  # Add 1s to the clock for each hit
                        break
        else:
            print("Ptr not found in ptr table.")

    def delete(self, ptr):
        if ptr in self.ptr_table:
            _, page_ids = self.ptr_table.pop(ptr)
            for index, page in enumerate(self.real_memory):
                if page and page.page_id in page_ids:
                    self.real_memory[index] = None
                    if index in self.mru_list:
                        self.mru_list.remove(index)
            if ptr in self.virtual_memory:
                del self.virtual_memory[ptr]
            print(f"Deleted ptr {ptr} and its associated pages from memory.")
        else:
            print("Ptr not found in ptr table.")

    def kill(self, pid):
        to_delete = [ptr_id for ptr_id, (pid_val, _) in self.ptr_table.items() if pid_val == pid]
        for ptr in to_delete:
            self.delete(ptr)
        print(f"All resources associated with PID {pid} have been successfully killed and freed.")

class Random_MMU:
    def __init__(self):
        self.real_memory = [None] * 100  # 100 pages in real memory
        self.virtual_memory = {}
        self.ptr_page_map = {}
        self.ptr_table = {}
        self.logical_page_counter = 1
        self.disk_page_counter = 1
        self.ptr_id_counter = 1
        self.clock = 0
        self.thrashing_time = 0

    def new(self, pid, size):
        num_pages = (size + 4095) // 4096
        ptr_id = self.ptr_id_counter
        self.ptr_id_counter += 1
        page_ids = []
        for _ in range(num_pages):
            logical_address = self.logical_page_counter
            if None not in self.real_memory:
                random_index = random.randint(0, 99)  # Randomly pick an index to replace
                self._evict_page(random_index)
                index = random_index
            else:
                index = self.real_memory.index(None)

            is_in_ram = True
            physical_address = index
            page = self._allocate_page(logical_address, is_in_ram, physical_address, None, pid)
            page_ids.append(page.page_id)
            self.real_memory[index] = page
            self.ptr_page_map[page.page_id] = ptr_id
            self.logical_page_counter += 1

        self.ptr_table[ptr_id] = (pid, page_ids)
        return ptr_id

    def _evict_page(self, index):
        evicted_page = self.real_memory[index]
        if evicted_page:
            old_ptr_id = self.ptr_page_map.get(evicted_page.page_id)
            if old_ptr_id:
                self.virtual_memory.setdefault(old_ptr_id, []).append({
                    'page_id': evicted_page.page_id,
                    'logical_address': evicted_page.logical_address,
                    'physical_address': None,
                    'disk_address': self.disk_page_counter,
                    'pid': evicted_page.pid
                })
                self.disk_page_counter += 1
            self.real_memory[index] = None
            self.clock += 5  # Simulate disk access time
            self.thrashing_time += 5  # Add to thrashing time

    def _allocate_page(self, logical_address, is_in_ram, physical_address, disk_address, pid):
        return Page(logical_address, is_in_ram, physical_address, disk_address, pid)

    def use(self, ptr):
        if ptr in self.ptr_table:
            _, page_ids = self.ptr_table[ptr]
            for page_id in page_ids:
                found = False
                for index, page in enumerate(self.real_memory):
                    if page and page.page_id == page_id:
                        self.clock += 1  # Add 1s to the clock for each hit
                        found = True
                        break
                if not found:
                    random_index = random.randint(0, 99)  # Randomly pick an index to replace for swap-in
                    self._evict_page(random_index)
                    self._allocate_page_to_ram(page_id, random_index)
        else:
            print("Ptr not found in ptr table.")

    def _allocate_page_to_ram(self, page_id, index):
        # Simulate fetching a page from virtual memory and placing it in real memory at the given index
        self.real_memory[index] = Page(page_id, True, index, None)  # Assume creation of the page object
        self.clock += 5
        self.thrashing_time += 5

    def delete(self, ptr):
        if ptr in self.ptr_table:
            _, page_ids = self.ptr_table.pop(ptr)
            for index, page in enumerate(self.real_memory):
                if page and page.page_id in page_ids:
                    self.real_memory[index] = None
            if ptr in self.virtual_memory:
                del self.virtual_memory[ptr]
            print(f"Deleted ptr {ptr} and its associated pages from memory.")
        else:
            print("Ptr not found in ptr table.")

    def kill(self, pid):
        to_delete = [ptr_id for ptr_id, (pid_val, _) in self.ptr_table.items() if pid_val == pid]
        for ptr in to_delete:
            self.delete(ptr)
        print(f"All resources associated with PID {pid} have been successfully killed and freed.")


