# Performance Model

“FTL” in Synapse OS means **minimize latency the human notices**, not violate physics.

## Default choices

- zram = 50% of RAM, zstd compression, high swap priority
- `vm.swappiness=80` so compressed-RAM swap can be preferred over disk pressure
- `vm.page-cluster=0` to reduce swap readahead that is often less useful for zram
- higher inotify limits for editors, build systems, and local AI repos
- `power-profiles-daemon` for hardware-supported performance/balanced/power-saver control
- PipeWire/WirePlumber for modern desktop audio routing

## Profiles

`pulse` asks the platform power-profile service for performance mode. It does not overclock the CPU/GPU or bypass thermal controls.

`balanced` is the default daily mode.

`quiet` requests power-saver mode for battery life and thermal headroom.

`auto` resolves to balanced on AC and quiet on battery.

## Benchmarking rule

Use `synapse bench` only as a same-machine smoke benchmark. Serious tuning should compare boot time, app launch latency, compile workloads, sustained thermal behavior, audio XRUNs, and energy usage with controlled repetitions.
