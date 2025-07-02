#!/usr/bin/env python3
import subprocess
import sys
import os
import datetime
import time as time_module # 避免和datetime模块的time冲突

def run_flamegraph_workflow():
    # --- 1. 处理 PID 和 TIME 参数 ---
    if len(sys.argv) < 2:
        print("Usage: python_flamegraph_script.py <PID> [TIME_IN_MINUTES]")
        sys.exit(1)

    pid = sys.argv[1]
    time_minutes = 1 # 默认60秒
    if len(sys.argv) > 2:
        try:
            time_minutes = int(sys.argv[2])
        except ValueError:
            print("Error: TIME_IN_MINUTES must be an integer.")
            sys.exit(1)

    sleep_time_seconds = time_minutes * 60

    # --- 2. 设置路径 ---
    # 获取当前脚本的目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 假设 FlameGraph 目录在与当前脚本同级的 'FlameGraph' 文件夹内
    flamegraph_dir = os.path.join(script_dir, 'FlameGraph')

    # 确保 FlameGraph 目录存在
    if not os.path.isdir(flamegraph_dir):
        print(f"Error: FlameGraph directory not found at {flamegraph_dir}")
        print("Please ensure the 'FlameGraph' folder is in the same directory as this script.")
        sys.exit(1)

    # --- 3. 生成文件名和清理旧文件 ---
    current_time_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    # 构建完整的文件路径
    perf_data_file = os.path.join(script_dir, f"perf_{current_time_str}.data")
    out_perf_file = os.path.join(script_dir, f"out_{current_time_str}.perf")
    out_folded_file = os.path.join(script_dir, f"out_{current_time_str}.folded")
    out_svg_file = os.path.join(script_dir, f"out_{current_time_str}.svg")

    # 清理旧文件 (可选，如果你希望每次运行都清理)
    # 你的bash脚本有 rm -f perf_*.data out_*.perf out_*.folded out_*.svg
    # 在 Python 中，我们可以更精确地删除：
    for f in os.listdir(script_dir):
        if f.startswith(('perf_', 'out_')) and \
           (f.endswith('.data') or f.endswith('.perf') or \
            f.endswith('.folded') or f.endswith('.svg')):
            try:
                os.remove(os.path.join(script_dir, f))
                # print(f"Removed old file: {f}") # 可以取消注释查看删除的文件
            except OSError as e:
                print(f"Error removing old file {f}: {e}")


    # --- 4. 执行 perf record ---
    print(f"Running: perf record -F 99 -g -p {pid} -o {perf_data_file} -- sleep {sleep_time_seconds}")
    try:
        subprocess.run(
            ["perf", "record", "-F", "99", "-g", "-p", pid, "-o", perf_data_file, "--", "sleep", str(sleep_time_seconds)],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"Error during perf record: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: 'perf' command not found. Please ensure perf is installed and in your PATH.")
        sys.exit(1)

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
        # 这个方法更通用，尝试获取主机的IP地址
        hostname_output = subprocess.check_output(["hostname", "-I"]).decode("utf-8").strip()
        ip_address = hostname_output.split()[0] if hostname_output else "127.0.0.1" # 如果获取不到，默认localhost
    except Exception:
        ip_address = "127.0.0.1" # 兜底方案


    # --- 9. 启动 HTTP 服务器 ---
    print(f"\nPlease access http://{ip_address}:8000/{os.path.basename(out_svg_file)}")
    print("Serving on port 8000 (Press Ctrl+C to stop)...")

    # 进入当前脚本的目录，以便http.server能正确找到out_*.svg文件
    os.chdir(script_dir) 
    
    try:
        import http.server
        import socketserver

        PORT = 8000
        Handler = http.server.SimpleHTTPRequestHandler
        
        # 允许地址重用，避免端口被占用
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