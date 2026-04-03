`timescale 1ns / 1ps

module life_cell (
    input wire [1:0] current_state, // 00=Empty, 01=A, 10=B
    input wire [3:0] nA_count,      // Number of A neighbors
    input wire [3:0] nB_count,      // Number of B neighbors
    output reg [1:0] next_state
);
    wire [3:0] total_neighbors;
    assign total_neighbors = nA_count + nB_count;

    always @(*) begin
        if (current_state == 2'b01 || current_state == 2'b10) begin
            // Rule 1 & 2: Survival and Death
            if (total_neighbors == 4'd2 || total_neighbors == 4'd3)
                next_state = current_state;
            else
                next_state = 2'b00;
        end else if (current_state == 2'b00 && total_neighbors == 4'd3) begin
            // Rule 3: Majority Birth
            if (nA_count > nB_count)
                next_state = 2'b01;
            else
                next_state = 2'b10;
        end else begin
            next_state = 2'b00;
        end
    end
endmodule