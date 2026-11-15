# Fix the uart_rx module

The cocotb testbench `tb/uart_rx` fails on this repository.

Observed: the test suite fails with the module in its current state (run logs in metadata.json under 'mutated'; 1.62s runtime, exit code 2).
Category hint: protocol-related functional defect in `rtl/uart_rx.v`.

Investigate the RTL, find the functional defect, and correct it while
preserving the module interface and all passing behavior.
