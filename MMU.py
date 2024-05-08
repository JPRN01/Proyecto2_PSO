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
        self.reference_bit = 0  # Bit R added for Second Chance logic

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

class SecondChance_MMU:
    def __init__(self):
        self.real_memory = [None] * 100
        self.virtual_memory = {}
        self.ptr_table = {}
        self.ptr_page_map = {}
        self.queue = []
        self.disk_page_counter = 1
        self.logical_page_counter = 1
        self.ptr_id_counter = 1
        self.clock = 0
        self.thrashing_time = 0

    def new(self, pid, size):
        num_pages = (size + 4095) // 4096
        ptr_id = self.ptr_id_counter
        self.ptr_id_counter += 1
        page_ids = []
        print(f"Starting new allocation: PID {pid}, size {size}, requiring {num_pages} pages.")
        for _ in range(num_pages):
            logical_address = self.logical_page_counter
            print(f"Checking for available memory slot for page {self.logical_page_counter}...")

            # Perform Second Chance algorithm if no free space is available
            if None not in self.real_memory:
                print("No free memory slots available. Initiating Second Chance algorithm...")
                self.perform_second_chance()

            index = self.real_memory.index(None) if None in self.real_memory else -1
            if index == -1:
                print("Critical Error: No memory available even after Second Chance processing.")
                break  # This should be handled more gracefully in a real system.

            # Allocate the new page
            page = Page(logical_address, True, index, None, pid)
            page_ids.append(page.page_id)
            self.real_memory[index] = page
            self.queue.append(index)
            self.ptr_page_map[page.page_id] = ptr_id

            print(f"Allocated page {page.page_id} at memory index {index}. Queue updated.")
            self.logical_page_counter += 1

        self.ptr_table[ptr_id] = (pid, page_ids)
        print(f"Allocation complete. Ptr {ptr_id} assigned to PID {pid} with pages {page_ids}.")
        return ptr_id


    def perform_second_chance(self):
        while True:
            oldest_index = self.queue.pop(0)
            oldest_page = self.real_memory[oldest_index]
            if oldest_page.reference_bit == 0:
                self.evict_page(oldest_page, oldest_index)
                break
            oldest_page.reference_bit = 0
            self.queue.append(oldest_index)

    def evict_page(self, page, index):
        old_ptr_id = self.ptr_page_map.get(page.page_id)
        if old_ptr_id:
            pid = self.ptr_table[old_ptr_id][0]
            self.virtual_memory.setdefault(old_ptr_id, []).append({
                'page_id': page.page_id,
                'logical_address': page.logical_address,
                'physical_address': None,
                'disk_address': self.disk_page_counter,
                'pid': pid
            })
            self.disk_page_counter += 1
        self.real_memory[index] = None
        print(f"Evicting page {page.page_id} from index {index}.")

    
    

    def use(self, ptr):
        if ptr in self.ptr_table:
            _, page_ids = self.ptr_table[ptr]
            print(f"Using ptr {ptr} with pages {page_ids}.")
            for page_id in page_ids:
                found_in_ram = False
                for index, page in enumerate(self.real_memory):
                    if page is not None and page.page_id == page_id:
                        found_in_ram = True
                        # Mark the page as recently used
                        page.reference_bit = 1
                        print(f"Page {page_id} is already in RAM. Setting reference bit.")
                        self.clock += 1  # Increment clock for each hit
                        break
                if not found_in_ram:
                    # Page is in virtual memory, need to swap it in
                    print(f"Page {page_id} is not in RAM, swapping from disk using Second Chance.")
                    self.clock += 5  # Increment clock for each miss
                    self.thrashing_time += 5  # Increment thrashing time
                    self._swap_page_to_ram(page_id)
        else:
            print("Ptr not found in ptr table.")

    def _swap_page_to_ram(self, page_id):
        print(f"Attempting to swap page {page_id} into RAM.")
        if None in self.real_memory:
            index = self.real_memory.index(None)
        else:
            # Apply Second Chance algorithm to find a page to evict
            self.perform_second_chance()
            index = self.queue.pop(0)  # Assume the page at the head of the queue is evictable now
            evicted_page = self.real_memory[index]
            print(f"No free space in real memory. Evicting page {evicted_page.page_id} from index {index}.")
            self.evict_page(evicted_page, index)

        # After space is made, place the new page in RAM
        found_page = False
        for ptr_id, pages in self.virtual_memory.items():
            for page in pages:
                if page['page_id'] == page_id:
                    # Use the existing page_id to maintain consistency
                    page_in_ram = Page(page['logical_address'], True, index, None, page.get('pid', None))
                    page_in_ram.page_id = page_id  # Ensure the original page ID is retained
                    self.real_memory[index] = page_in_ram
                    self.queue.append(index)  # Add to the end of the queue with the reference bit set
                    page_in_ram.reference_bit = 1  # Set the reference bit when the page is brought into RAM
                    pages.remove(page)
                    self.ptr_page_map[page_id] = ptr_id
                    print(f"Swapped page {page_id} into RAM at index {index}. Page details: {page_in_ram.__dict__}")
                    found_page = True
                    break
            if found_page:
                break

        if not found_page:
            print(f"Error: Page {page_id} not found in virtual memory for swapping.")



    def print_fifo_queue(self):
        print("FIFO Queue Content:")
        for index in self.queue:
            page = self.real_memory[index]
            if page:
                print(f"Index {index}: Page ID {page.page_id}, Logical Address {page.logical_address}, Reference Bit {page.reference_bit}, In RAM {page.is_in_ram}")
            else:
                print(f"Index {index}: Empty slot")

    def print_physical_memory_state(self):
        print("Physical Memory State:")
        for index, page in enumerate(self.real_memory):
            if page:
                # Retrieve the ptr_id and pid associated with the page
                ptr_id = self.ptr_page_map.get(page.page_id, "Unknown Pointer")
                pid = self.ptr_table.get(ptr_id, ("Unknown PID", []))[0] if ptr_id != "Unknown Pointer" else "Unknown PID"
                
                # Print detailed information about each page
                print(f"Index {index}: Page ID {page.page_id}, Logical Address {page.logical_address}, "
                    f"Physical Address {index}, Reference Bit {page.reference_bit}, In RAM {page.is_in_ram}, "
                    f"Ptr ID {ptr_id}, PID {pid}")
            else:
                print(f"Index {index}: Empty slot")


    def print_virtual_memory(self):
        print("Virtual Memory Content:")
        for ptr_id, pages in self.virtual_memory.items():
            for page in pages:
                print(f"Ptr {ptr_id}: Page ID {page['page_id']}, Logical Address {page['logical_address']}, Disk Address {page['disk_address']}, PID {page['pid']}")

class FIFO_MMU:
    def __init__(self):
        self.real_memory = [None] * 100
        self.virtual_memory = {}
        self.ptr_table = {}
        self.ptr_page_map = {}
        self.queue = []
        self.disk_page_counter = 1
        self.logical_page_counter = 1
        self.ptr_id_counter = 1
        self.clock = 0  
        self.thrashing_time = 0  

    def new(self, pid, size):
        num_pages = (size + 4095) // 4096
        ptr_id = self.ptr_id_counter
        self.ptr_id_counter += 1
        page_ids = []
        print(f"Starting new allocation: PID {pid}, size {size}, requiring {num_pages} pages.")
        for _ in range(num_pages):
            logical_address = self.logical_page_counter
            print(f"Allocating page {self.logical_page_counter} at logical address {logical_address}.")
            if None not in self.real_memory:
                oldest_page_index = self.queue.pop(0)
                oldest_page = self.real_memory[oldest_page_index]
                old_ptr_id = self.ptr_page_map[oldest_page.page_id]
                pid_old = self.ptr_table[old_ptr_id][0]  # Retrieve the PID associated with the oldest page
                print(f"No free space in real memory. Evicting page {oldest_page.page_id} from index {oldest_page_index}.")
                self.virtual_memory.setdefault(old_ptr_id, []).append({
                    'page_id': oldest_page.page_id,
                    'logical_address': oldest_page.logical_address,
                    'physical_address': None,
                    'disk_address': self.disk_page_counter,
                    'pid': pid_old  # Store PID along with other page details
                })
                self.disk_page_counter += 1
                self.real_memory[oldest_page_index] = None
                self.clock += 5  # Sumar 5 segundos por fallo
                self.thrashing_time += 5  # Sumar al tiempo de thrashing
                index = oldest_page_index
            else:
                index = self.real_memory.index(None)
                self.clock += 1
                print(f"Found free space in real memory at index {index}.")

            is_in_ram = index != -1
            physical_address = index if is_in_ram else None
            disk_address = None if is_in_ram else self.disk_page_counter
            if not is_in_ram:
                self.disk_page_counter += 1

            page = self._allocate_page(logical_address, is_in_ram, physical_address, disk_address, pid)
            page_ids.append(page.page_id)
            self.real_memory[index] = page
            self.queue.append(index)
            self.ptr_page_map[page.page_id] = ptr_id
            print(f"Page {page.page_id} added to real memory at index {index}. Now in RAM: {is_in_ram}")

            self.logical_page_counter += 1

        self.ptr_table[ptr_id] = (pid, page_ids)
        print(f"Allocation complete. Ptr {ptr_id} assigned to PID {pid} with pages {page_ids}.")
        return ptr_id

    def use(self, ptr):
        if ptr in self.ptr_table:
            _, page_ids = self.ptr_table[ptr]
            print(f"Using ptr {ptr} with pages {page_ids}.")
            for page_id in page_ids:
                found_in_ram = False
                for index, page in enumerate(self.real_memory):
                    if page is not None and page.page_id == page_id:
                        found_in_ram = True
                        # Move this page's index to the end of the FIFO queue
                        if index in self.queue:
                            self.queue.remove(index)
                        self.queue.append(index)
                        print(f"Page {page_id} is already in RAM and has been refreshed in the FIFO queue.")
                        self.clock += 1  # Sumar 1s al reloj por cada hit
                        break
                if not found_in_ram:
                    # Page is in virtual memory, need to swap it in
                    print(f"Page {page_id} is not in RAM, swapping from disk.")
                    self.clock += 5  # Sumar 5s al reloj por cada fallo
                    self.thrashing_time += 5  # Sumar al tiempo de thrashing
                    self._swap_page_to_ram(page_id)
        else:
            print("Ptr not found in ptr table.")

    def _swap_page_to_ram(self, page_id):
        print(f"Attempting to swap page {page_id} into RAM.")
        if None in self.real_memory:
            index = self.real_memory.index(None)
        else:
            index = self.queue.pop(0)
            evicted_page = self.real_memory[index]
            print(f"No free space in real memory. Evicting page {evicted_page.page_id} from index {index}.")
            old_ptr_id = self.ptr_page_map.get(evicted_page.page_id)
            if old_ptr_id is not None:
                pid = self.ptr_table[old_ptr_id][0]

                self.virtual_memory.setdefault(old_ptr_id, []).append({
                    'page_id': evicted_page.page_id,
                    'logical_address': evicted_page.logical_address,
                    'physical_address': None,
                    'disk_address': self.disk_page_counter,
                    'pid': pid 

                })
                self.disk_page_counter += 1
            self.real_memory[index] = None

        found_page = False
        for ptr_id, pages in self.virtual_memory.items():
            for page in pages:
                if page['page_id'] == page_id:
                    # Use the existing page_id to maintain consistency
                    pid = page.get('pid', None)
                    page_in_ram = Page(page['logical_address'], True, index, None)
                    page_in_ram.page_id = page_id  # Ensure the original page ID is retained
                    self.real_memory[index] = page_in_ram
                    self.queue.append(index)  # Add to the end of the FIFO queue
                    pages.remove(page)
                    self.ptr_page_map[page_id] = ptr_id
                    print(f"Swapped page {page_id} into RAM at index {index}. Page details: {page_in_ram.__dict__}")
                    found_page = True
                    break
            if found_page:
                break

        if not found_page:
            print(f"Error: Page {page_id} not found in virtual memory for swapping.")

    def delete(self, ptr):
        if ptr in self.ptr_table:
            _, page_ids = self.ptr_table.pop(ptr)
            print(f"Deleting ptr {ptr} with pages {page_ids}.")
            updated_real_memory = []
            for index, page in enumerate(self.real_memory):
                if page is None or page.page_id not in page_ids:
                    updated_real_memory.append(page)
                else:
                    updated_real_memory.append(None)
                    if index in self.queue:
                        self.queue.remove(index)
            self.real_memory = updated_real_memory

            if ptr in self.virtual_memory:
                del self.virtual_memory[ptr]
            print(f"All pages for ptr {ptr} removed from memory. Ptr table entry removed.")
        else:
            print("Ptr not found in ptr table.")

    def kill(self, pid):
        # Primero, buscar todos los ptrs asociados con este pid y eliminarlos
        ptrs_to_delete = [ptr_id for ptr_id, (pid_val, _) in self.ptr_table.items() if pid_val == pid]
        for ptr_id in ptrs_to_delete:
            self.delete(ptr_id)
            
        # Asegurarse de que tambiÃ©n se eliminan de la memoria virtual
        for ptr_id in list(self.virtual_memory.keys()):
            if ptr_id in ptrs_to_delete:
                del self.virtual_memory[ptr_id]

        # Finalmente, remover cualquier pÃ¡gina que pueda estar en la memoria real pero que no se limpiÃ³ completamente
        self.real_memory = [None if (page and self.ptr_page_map.get(page.page_id) in ptrs_to_delete) else page for page in self.real_memory]

        # Limpiar la cola FIFO para las pÃ¡ginas que ya no son vÃ¡lidas
        self.queue = [index for index in self.queue if self.real_memory[index] and self.ptr_page_map.get(self.real_memory[index].page_id) not in ptrs_to_delete]
        
        print(f"All resources associated with PID {pid} have been successfully killed and freed.")


    def _allocate_page(self, logical_address, is_in_ram, physical_address, disk_address, pid):
        # The method now takes an additional 'pid' parameter and passes it to the Page constructor
        return Page(logical_address, is_in_ram, physical_address, disk_address, pid)


    def print_virtual_memory(self):
        print("Virtual Memory Content:")
        for ptr_id, pages in self.virtual_memory.items():
            for page in pages:
                # Fetching PID from each page information
                pid = page.get('pid', 'Unknown PID')
                print(f"Ptr {ptr_id}: Page ID {page['page_id']}, Physical Address: {page['physical_address']}, Disk Address: {page['disk_address']}, PID: {pid}")


    def print_fifo_queue(self):
        print("FIFO Queue Content:")
        for index in self.queue:
            page = self.real_memory[index]
            if page:
                print(f"Index {index} in real memory: Page ID {page.page_id}, Logical Address {page.logical_address}, In RAM {page.is_in_ram}")
            else:
                print(f"Index {index} in real memory: Empty slot")

    def print_physical_memory_state(self):
        print("Physical Memory State:")
        for index, page in enumerate(self.real_memory):
            if page:
                ptr_id = self.ptr_page_map.get(page.page_id, "Unknown Pointer")
                pid = self.ptr_table.get(ptr_id, ("Unknown PID", []))[0] if ptr_id != "Unknown Pointer" else "Unknown PID"
                print(f"Index {index}: Page ID {page.page_id}, Logical Address {page.logical_address}, Physical Address {index}, In RAM {page.is_in_ram}, Belongs to PID {pid}, Ptr {ptr_id}")
            else:
                print(f"Index {index}: Empty slot")


    def print_time(self):
        print(f"Total time elapsed: {self.clock} seconds")
        print(f"Total thrashing time: {self.thrashing_time} seconds")
