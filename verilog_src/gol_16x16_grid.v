`timescale 1ns / 1ps

module gol_16x16_grid (
    input wire clk,
    input wire rst,
    input wire start,
    input wire [1:0] flat_grid_in [0:255], // Initial placement from Python
    output reg done,
    output reg [7:0] pop_A,
    output reg [7:0] pop_B
);

    // 2D Array to hold the current state of the board
    reg [1:0] grid [0:15][0:15];
    wire [1:0] next_grid [0:15][0:15];
    
    reg [6:0] step_counter;
    reg running;

    // --- Generate 256 Cells and Neighbor Routing ---
    genvar r, c;
    generate
        for (r = 0; r < 16; r = r + 1) begin : row_gen
            for (c = 0; c < 16; c = c + 1) begin : col_gen
                
                wire [3:0] count_A, count_B;
                
                // Combinational neighbor counting with Hard Boundaries
                assign count_A = 
                    ((r>0 && c>0) ? (grid[r-1][c-1] == 2'b01) : 0) +
                    ((r>0)        ? (grid[r-1][c]   == 2'b01) : 0) +
                    ((r>0 && c<15)? (grid[r-1][c+1] == 2'b01) : 0) +
                    ((c>0)        ? (grid[r][c-1]   == 2'b01) : 0) +
                    ((c<15)       ? (grid[r][c+1]   == 2'b01) : 0) +
                    ((r<15 && c>0)? (grid[r+1][c-1] == 2'b01) : 0) +
                    ((r<15)       ? (grid[r+1][c]   == 2'b01) : 0) +
                    ((r<15 && c<15)?(grid[r+1][c+1] == 2'b01) : 0);
                    
                assign count_B = 
                    ((r>0 && c>0) ? (grid[r-1][c-1] == 2'b10) : 0) +
                    ((r>0)        ? (grid[r-1][c]   == 2'b10) : 0) +
                    ((r>0 && c<15)? (grid[r-1][c+1] == 2'b10) : 0) +
                    ((c>0)        ? (grid[r][c-1]   == 2'b10) : 0) +
                    ((c<15)       ? (grid[r][c+1]   == 2'b10) : 0) +
                    ((r<15 && c>0)? (grid[r+1][c-1] == 2'b10) : 0) +
                    ((r<15)       ? (grid[r+1][c]   == 2'b10) : 0) +
                    ((r<15 && c<15)?(grid[r+1][c+1] == 2'b10) : 0);

                life_cell cell_inst (
                    .current_state(grid[r][c]),
                    .nA_count(count_A),
                    .nB_count(count_B),
                    .next_state(next_grid[r][c])
                );
            end
        end
    endgenerate

    // --- State Machine ---
    integer i, j;
    always @(posedge clk) begin
        if (rst) begin
            step_counter <= 0;
            running <= 0;
            done <= 0;
            pop_A <= 0;
            pop_B <= 0;
        end else if (start && !running && !done) begin
            // Load initial data from Python
            for (i=0; i<16; i=i+1) begin
                for (j=0; j<16; j=j+1) begin
                    grid[i][j] <= flat_grid_in[(i*16)+j];
                end
            end
            running <= 1;
            step_counter <= 0;
        end else if (running) begin
            if (step_counter < 100) begin
                // Update grid simultaneously
                for (i=0; i<16; i=i+1) begin
                    for (j=0; j<16; j=j+1) begin
                        grid[i][j] <= next_grid[i][j];
                    end
                end
                step_counter <= step_counter + 1;
            end else begin
                // 100 Steps finished, calculate final population
                running <= 0;
                done <= 1;
                // Note: In real hardware, pop counting is usually spread over a few clock cycles 
                // to meet timing, but for 16x16 this combinational sum will likely pass.
                pop_A <= 0; pop_B <= 0;
                for (i=0; i<16; i=i+1) begin
                    for (j=0; j<16; j=j+1) begin
                        if (grid[i][j] == 2'b01) pop_A <= pop_A + 1;
                        if (grid[i][j] == 2'b10) pop_B <= pop_B + 1;
                    end
                end
            end
        end
    end
endmodule