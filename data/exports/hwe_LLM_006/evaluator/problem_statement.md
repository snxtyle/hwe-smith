# Fix the uart_tx module

The cocotb testbench `tb/uart_tx` fails on this repository.

Observed: the test suite fails with the module in its current state (run logs in metadata.json under 'mutated'; 60.05s runtime, exit code -9).
Category hint: handshake-related functional defect in `rtl/uart_tx.v`.

Investigate the RTL, find the functional defect, and correct it while
preserving the module interface and all passing behavior.
