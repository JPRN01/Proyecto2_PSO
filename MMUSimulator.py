import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import re

# Importación de los módulos MMU
from MMU import OPT_MMU, MRU_MMU, Random_MMU, FIFO_MMU, SecondChance_MMU

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import re


class MMUSimulator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MMU Simulation")
        self.geometry("1400x900")
        self.algorithms = {
            'MRU': MRU_MMU(),
            'Random': Random_MMU(),
            'FIFO': FIFO_MMU(),
            'SecondChance': SecondChance_MMU()
        }
        self.current_mmu = None
        self.is_simulation_running = False
        self.create_initial_widgets()
        self.create_simulation_widgets()

    def update_treeview(self, tree, memory_state):
        tree.delete(*tree.get_children())
        for page in memory_state:
            if page is not None:  # Ensure the page is not None before accessing its properties
                tree.insert('', 'end', values=(page.page_id, page.pid, page.is_in_ram,
                                               page.logical_address, page.physical_address,
                                               page.disk_address, "Loaded-TBD"))

    def simulate_step(self):
        if not self.operations:
            messagebox.showinfo("Simulation Complete", "No more operations to process.")
            self.is_simulation_running = False
            return

        command, args = self.operations.pop(0)
        try:
            # Process the command using current MMU and get memory states
            if command == "new":
                ptr = self.current_mmu.new(*args)
                print(f"New process created with pointer {ptr}")
            elif command == "use":
                self.current_mmu.use(*args)
            elif command == "delete":
                self.current_mmu.delete(*args)
            elif command == "kill":
                self.current_mmu.kill(*args)
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
            self.is_simulation_running = False
            return

        # Update tree views
        self.update_treeview(self.tree_opt, self.current_mmu.real_memory)
        self.update_treeview(self.tree_alg, self.current_mmu.real_memory)  # Update this line based on actual structure

        if self.is_simulation_running:
            self.after(1000, self.simulate_step)  # Simulate next step after 1 second

    def start_simulation(self):
        if not self.current_mmu or not self.operations:
            messagebox.showerror("Error", "MMU not selected or no operations loaded.")
            return

        self.is_simulation_running = True
        self.simulate_step()

    def setup_treeview(self, parent, name):
        tree = ttk.Treeview(parent, columns=("Page ID", "PID", "Loaded", "L-ADDR", "M-ADDR", "D-ADDR", "Loaded-T"),
                            show="headings")
        for col in ("Page ID", "PID", "Loaded", "L-ADDR", "M-ADDR", "D-ADDR", "Loaded-T"):
            tree.heading(col, text=col)
        tree.pack(fill='both', expand=True)
        return tree

    def create_simulation_widgets(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True)
        self.tab_opt = ttk.Frame(self.notebook)
        self.tab_alg = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_opt, text='OPT Memory State')
        self.notebook.add(self.tab_alg, text='Selected Algorithm Memory State')
        self.tree_opt = self.setup_treeview(self.tab_opt, "OPT")
        self.tree_alg = self.setup_treeview(self.tab_alg, "Selected Algorithm")

    def create_initial_widgets(self):
        control_frame = ttk.Frame(self)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(control_frame, text="Select Algorithm:").pack(side=tk.LEFT, padx=10)
        self.algorithm_var = tk.StringVar()
        self.algorithm_selector = ttk.Combobox(control_frame, textvariable=self.algorithm_var,
                                               values=list(self.algorithms.keys()), state="readonly")
        self.algorithm_selector.pack(side=tk.LEFT, padx=10)
        self.algorithm_selector.bind("<<ComboboxSelected>>", self.update_current_mmu)

        self.load_button = ttk.Button(control_frame, text="Load Operations", command=self.load_operations)
        self.load_button.pack(side=tk.LEFT, padx=10)

        self.start_button = ttk.Button(control_frame, text="Start Simulation", state=tk.DISABLED,
                                       command=self.start_simulation)
        self.start_button.pack(side=tk.LEFT, padx=10)

    def update_current_mmu(self, event=None):
        selected_algorithm = self.algorithm_var.get()
        self.current_mmu = self.algorithms[selected_algorithm]
        print(f"Algorithm {selected_algorithm} selected, MMU initialized.")

    def load_operations(self):
        filepath = filedialog.askopenfilename()
        if filepath:
            print(f"Loaded operations from {filepath}")
            self.operations = []
            with open(filepath, "r") as file:
                for line in file:
                    parts = re.findall(r"(\w+)\(([\d,\s]+)\)", line.strip())
                    if parts:
                        command, args_str = parts[0]
                        args = [int(x.strip()) for x in args_str.split(',')]
                        self.operations.append((command, args))
            print(f"Loaded {len(self.operations)} operations.")
            if self.current_mmu and self.operations:
                self.start_button['state'] = tk.NORMAL

    def process_operations(self):
        for command, args in self.operations:
            try:
                if command == "new":
                    pid, size = args
                    ptr = self.current_mmu.new(pid, size)
                    print(f"Created new process {pid} with size {size}, pointer {ptr}")
                elif command == "use":
                    ptr = args[0]
                    self.current_mmu.use(ptr)
                    print(f"Used pointer {ptr}")
                elif command == "delete":
                    ptr = args[0]
                    self.current_mmu.delete(ptr)
                    print(f"Deleted pointer {ptr}")
                elif command == "kill":
                    pid = args[0]
                    self.current_mmu.kill(pid)
                    print(f"Killed process {pid}")
                else:
                    print(f"Unknown command {command}")
            except Exception as e:
                print(f"Error processing command {command}: {str(e)}")


if __name__ == "__main__":
    app = MMUSimulator()
    app.mainloop()
