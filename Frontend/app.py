from flask import Flask, render_template, jsonify
from pynq import Overlay
import time
import google.generativeai as genai # Assuming we use Gemini for the AI

app = Flask(__name__)

# --- 1. SETUP AI ---
genai.configure(api_key="YOUR_API_KEY_HERE")
model = genai.GenerativeModel('gemini-1.5-flash')

# --- 2. SETUP HARDWARE ---
print("Loading FPGA Overlay...")
overlay = Overlay("gameoflife.bit")
hw = overlay.GameOfLife_AXI_0
print("FPGA Ready!")

# --- 3. GAME STATE ---
# For the demo, we'll pre-load a cool "battle" layout
grid_size = 16
grid = [[0 for _ in range(grid_size)] for _ in range(grid_size)]
# Put a Glider for Player A (1) and a Block for Player B (2) to give the AI something to look at
grid[1][1]=1; grid[2][2]=1; grid[2][3]=1; grid[1][3]=1; grid[0][2]=1 
grid[10][10]=2; grid[10][11]=2; grid[11][10]=2; grid[11][11]=2 

# --- 4. FLASK ROUTES ---
@app.route('/')
def home():
    """Serves the Cyberpunk HTML page"""
    return render_template('index.html', initial_grid=grid)

@app.route('/scan_board')
def scan_board():
    """Takes the current grid, converts it to text, and asks the LLM for strategy."""
    # Convert grid to a string of numbers
    grid_str = "\n".join([" ".join([str(cell) for cell in row]) for row in grid])
    
    prompt = f"""
    You are a grandmaster of the Game of Life. 
    Map Legend: 0=Empty, 1=Player A, 2=Player B.
    
    Current Board State:
    {grid_str}
    
    It is Player A's turn. Analyze the clusters. Reply with 2-3 short, punchy, tactical sentences.
    Tell them EXACT coordinates (row, col) to place a cell to disrupt Player B or help Player A.
    Keep it aggressive and in a 'Cyberpunk Tactical Analyst' tone. No markdown, just text.
    """
    
    try:
        response = model.generate_content(prompt)
        return jsonify({"feedback": response.text})
    except Exception as e:
        return jsonify({"feedback": f"UPLINK FAILED: {str(e)}"})

@app.route('/run_fpga')
def run_fpga():
    """Sends the grid to the FPGA, runs 100 steps instantly, and returns the result."""
    start_time = time.time()
    
    # 1. Write grid to FPGA registers
    for r in range(16):
        row_data = 0
        for c in range(16):
            row_data |= (grid[r][c] << (c * 2)) 
        hw.write(0x08 + (r * 4), row_data)

    # 2. Fire the Start Signal
    hw.write(0x00, 1)

    # 3. Wait for FPGA to finish
    while (hw.read(0x04) & 0x01) == 0:
        pass

    # 4. Read Results
    status = hw.read(0x04)
    pop_A = (status >> 8) & 0xFF
    pop_B = (status >> 16) & 0xFF
    hw.write(0x00, 0) # Reset
    
    end_time = time.time()
    calc_time = (end_time - start_time) * 1000 # milliseconds

    result_text = f"FPGA CALCULATION COMPLETE ({calc_time:.3f}ms). A: {pop_A} | B: {pop_B}"
    return jsonify({"status": result_text})

# --- Add this helper function somewhere above your routes ---
def calculate_single_step():
    global grid
    new_grid = [[0 for _ in range(grid_size)] for _ in range(grid_size)]
    p_A, p_B = 0, 0

    for r in range(grid_size):
        for c in range(grid_size):
            # Count neighbors
            n_A, n_B = 0, 0
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    if dr == 0 and dc == 0: continue
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < grid_size and 0 <= nc < grid_size:
                        if grid[nr][nc] == 1: n_A += 1
                        elif grid[nr][nc] == 2: n_B += 1
            
            total = n_A + n_B
            current = grid[r][c]

            # Rules
            if current in (1, 2):
                if total in (2, 3): 
                    new_grid[r][c] = current
                    if current == 1: p_A += 1
                    else: p_B += 1
            elif current == 0 and total == 3:
                if n_A > n_B:
                    new_grid[r][c] = 1
                    p_A += 1
                else:
                    new_grid[r][c] = 2
                    p_B += 1
                    
    grid = new_grid # Update the global board state
    return p_A, p_B

# --- Add this new route for the animation ---
@app.route('/step_frame')
def step_frame():
    """Calculates one frame in Python and returns the new grid for animation."""
    p_A, p_B = calculate_single_step()
    return jsonify({"grid": grid, "pop_A": p_A, "pop_B": p_B})

@app.route('/load_fpga')
def load_fpga():
    """Writes the initial grid to the FPGA and fires the LOAD signal."""
    for r in range(16):
        row_data = 0
        for c in range(16):
            row_data |= (grid[r][c] << (c * 2)) 
        hw.write(0x08 + (r * 4), row_data)
        
    hw.write(0x00, 1) # Load High
    hw.write(0x00, 0) # Load Low
    return jsonify({"status": "Hardware Loaded"})

@app.route('/step_fpga')
def step_fpga():
    """Tells the FPGA to advance 1 tick, then reads the live grid back."""
    # 1. Fire STEP
    hw.write(0x00, 2) # Step High
    hw.write(0x00, 0) # Step Low
    
    # 2. Read the live grid out of the FPGA
    current_grid = [[0 for _ in range(16)] for _ in range(16)]
    for r in range(16):
        row_data = hw.read(0x08 + (r * 4))
        for c in range(16):
            current_grid[r][c] = (row_data >> (c * 2)) & 0b11
            
    # 3. Read the populations
    status = hw.read(0x04)
    pop_A = (status >> 8) & 0xFF
    pop_B = (status >> 16) & 0xFF
    
    return jsonify({"grid": current_grid, "pop_A": pop_A, "pop_B": pop_B})

@app.route('/update_cell/<int:r>/<int:c>')
def update_cell(r, c):
    """Toggles a cell: Empty (0) -> Player A (1) -> Player B (2) -> Empty (0)"""
    global grid
    current_val = grid[r][c]
    new_val = (current_val + 1) % 3
    grid[r][c] = new_val
    
    return jsonify({"status": "success", "new_val": new_val})

if __name__ == '__main__':
    # Runs the server on port 5000, accessible to anyone on the network
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)