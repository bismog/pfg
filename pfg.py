#!/usr/bin/env python3
import subprocess
import sys
import os
import datetime

def run_flamegraph_workflow():
    # --- 1. 处理参数 ---
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Mode 1 (PID): python_flamegraph_script.py <PID> [TIME_IN_MINUTES]")
        print("  Mode 2 (CMD): python_flamegraph_script.py --cmd <COMMAND> [ARGS...]")
        print("\nExamples:")
        print("  python_flamegraph_script.py 1234 5")
        print("  python_flamegraph_script.py --cmd iptables-save")
        print("  python_flamegraph_script.py --cmd python my_script.py --arg1 --arg2")
        sys.exit(1)

    # 判断模式
    mode = "pid"  # 默认 PID 模式
    pid = None
    command = None
    time_minutes = 1  # 默认 1 分钟

    if sys.argv[1] == "--cmd":
        mode = "cmd"
        if len(sys.argv) < 3:
            print("Error: --cmd requires a command to run")
            sys.exit(1)
        command = sys.argv[2:]  # 获取所有后续参数作为命令
    else:
        mode = "pid"
        pid = sys.argv[1]
        if len(sys.argv) > 2:
            try:
                time_minutes = int(sys.argv[2])
            except ValueError:
                print("Error: TIME_IN_MINUTES must be an integer.")
                sys.exit(1)

    sleep_time_seconds = time_minutes * 60

    # --- 2. 设置路径 ---
    script_dir = os.path.dirname(os.path.abspath(__file__))
    flamegraph_dir = os.path.join(script_dir, 'FlameGraph')

    if not os.path.isdir(flamegraph_dir):
        print(f"Error: FlameGraph directory not found at {flamegraph_dir}")
        print("Please ensure the 'FlameGraph' folder is in the same directory as this script.")
        sys.exit(1)

    # --- 3. 生成文件名和清理旧文件 ---
    current_time_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    perf_data_file = os.path.join(script_dir, f"perf_{current_time_str}.data")
    out_perf_file = os.path.join(script_dir, f"out_{current_time_str}.perf")
    out_folded_file = os.path.join(script_dir, f"out_{current_time_str}.folded")
    out_svg_file = os.path.join(script_dir, f"out_{current_time_str}.svg")

    # 清理旧文件
    for f in os.listdir(script_dir):
        if f.startswith(('perf_', 'out_')) and \
           (f.endswith('.data') or f.endswith('.perf') or \
            f.endswith('.folded') or f.endswith('.svg')):
            try:
                os.remove(os.path.join(script_dir, f))
            except OSError as e:
                print(f"Error removing old file {f}: {e}")

    # --- 4. 执行 perf record ---
    if mode == "pid":
        print(f"Running: perf record -F 99 -g -p {pid} -o {perf_data_file} -- sleep {sleep_time_seconds}")
        perf_cmd = ["perf", "record", "-F", "99", "-g", "-p", pid, "-o", perf_data_file, "--", "sleep", str(sleep_time_seconds)]
    else:  # cmd mode
        cmd_str = " ".join(command)
        print(f"Running: perf record -F 99 -g -o {perf_data_file} -- {cmd_str}")
        perf_cmd = ["perf", "record", "-F", "99", "-g", "-o", perf_data_file, "--"] + command

    try:
        subprocess.run(perf_cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error during perf record: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: 'perf' command not found. Please ensure perf is installed and in your PATH.")
        sys.exit(1)

    # 检查是否生成了 perf.data 文件
    if not os.path.exists(perf_data_file):
        print(f"Error: {perf_data_file} was not created. The command may have failed or no samples were collected.")
        sys.exit(1)

    # 检查 perf.data 文件大小
    file_size = os.path.getsize(perf_data_file)
    if file_size < 1024:  # 小于 1KB 可能没有采集到数据
        print(f"Warning: {perf_data_file} is very small ({file_size} bytes). May not have collected enough samples.")

    # --- 5. 执行 perf script ---
    print(f"Running: perf script -i {perf_data_file} > {out_perf_file}")
    try:
        with open(out_perf_file, "w") as f:
            subprocess.run(
                ["perf", "script", "-i", perf_data_file],
                stdout=f,
                check=True
            )
    except subprocess.CalledProcessError as e:
        print(f"Error during perf script: {e}")
        sys.exit(1)

    # --- 6. 执行 stackcollapse-perf.pl ---
    stackcollapse_script = os.path.join(flamegraph_dir, "stackcollapse-perf.pl")
    print(f"Running: {stackcollapse_script} {out_perf_file} > {out_folded_file}")
    try:
        with open(out_folded_file, "w") as f_out:
            with open(out_perf_file, "r") as f_in:
                subprocess.run(
                    ["perl", stackcollapse_script],
                    stdin=f_in,
                    stdout=f_out,
                    check=True
                )
    except subprocess.CalledProcessError as e:
        print(f"Error during stackcollapse-perf.pl: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: 'perl' command not found. Please ensure Perl is installed and in your PATH.")
        sys.exit(1)

    # --- 7. 执行 flamegraph.pl ---
    flamegraph_script = os.path.join(flamegraph_dir, "flamegraph.pl")
    print(f"Running: {flamegraph_script} {out_folded_file} > {out_svg_file}")
    try:
        with open(out_svg_file, "w") as f_out:
            with open(out_folded_file, "r") as f_in:
                subprocess.run(
                    ["perl", flamegraph_script],
                    stdin=f_in,
                    stdout=f_out,
                    check=True
                )
    except subprocess.CalledProcessError as e:
        print(f"Error during flamegraph.pl: {e}")
        sys.exit(1)

    # --- 8. 获取本机 IP 地址 ---
    try:
        hostname_output = subprocess.check_output(["hostname", "-I"]).decode("utf-8").strip()
        ip_address = hostname_output.split()[0] if hostname_output else "127.0.0.1"
    except Exception:
        ip_address = "127.0.0.1"

    # --- 9. 启动 HTTP 服务器 ---
    print(f"\nFlamegraph generated successfully!")
    print(f"Please access http://{ip_address}:8000/{os.path.basename(out_svg_file)}")
    print("Serving on port 8000 (Press Ctrl+C to stop)...")

    os.chdir(script_dir)
    
    try:
        import http.server
        import socketserver

        PORT = 8000
        Handler = http.server.SimpleHTTPRequestHandler
        
        socketserver.TCPServer.allow_reuse_address = True
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print("Serving HTTP on port", PORT)
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nHTTP server stopped.")
    except Exception as e:
        print(f"Error starting HTTP server: {e}")

if __name__ == "__main__":
    run_flamegraph_workflow()
