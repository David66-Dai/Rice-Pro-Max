import json
from typing import Any

import requests


class hdfs:
    def __init__(
        self,
        namenode_host: str,
        namenode_port: int = 9870,
        user: str = "hdfs",
        timeout: int = 30,
    ) -> None:
        """建立一个 WebHDFS 连接配置。

        传入一次主机地址、端口、用户名后，后续调用 mkdirs / upload_json /
        upload_file 等方法时只需传操作相关参数即可。
        """
        self.namenode_host = namenode_host
        self.namenode_port = namenode_port
        self.user = user
        self.timeout = timeout

    def _build_url(self, hdfs_path: str, query: str) -> str:
        if not hdfs_path.startswith("/"):
            raise ValueError("hdfs_path 必须是绝对路径，例如 /user/danglong/output/a.json")
        return f"http://{self.namenode_host}:{self.namenode_port}/webhdfs/v1{hdfs_path}?{query}"

    def _with_user(self, query: str) -> str:
        return f"{query}&user.name={self.user}"

    def mkdirs(
        self,
        hdfs_dir: str,
        error_if_exists: bool = False,
        timeout: int | None = None,
    ) -> None:
        effective_timeout = timeout if timeout is not None else self.timeout

        if error_if_exists:
            status_url = self._build_url(hdfs_dir, self._with_user("op=GETFILESTATUS"))
            status_resp = requests.get(status_url, timeout=effective_timeout)
            if status_resp.status_code == 200:
                raise FileExistsError(f"HDFS 目录已存在: {hdfs_dir}")
            if status_resp.status_code != 404:
                status_resp.raise_for_status()

        url = self._build_url(hdfs_dir, self._with_user("op=MKDIRS"))
        resp = requests.put(url, timeout=effective_timeout)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("boolean", False):
            raise RuntimeError(f"创建目录失败: {hdfs_dir}, 响应: {data}")

    def upload_json(
        self,
        data: dict[str, Any],
        hdfs_path: str,
        overwrite: bool = True,
        timeout: int | None = None,
    ) -> None:
        effective_timeout = timeout if timeout is not None else self.timeout

        step1_url = self._build_url(
            hdfs_path,
            self._with_user(f"op=CREATE&overwrite={'true' if overwrite else 'false'}"),
        )
        step1_resp = requests.put(step1_url, allow_redirects=False, timeout=effective_timeout)
        step1_resp.raise_for_status()

        if step1_resp.status_code == 201:
            return
        if step1_resp.status_code != 307:
            raise RuntimeError(
                f"CREATE 第一步返回异常: status={step1_resp.status_code}, body={step1_resp.text}"
            )

        location = step1_resp.headers.get("Location")
        if not location:
            raise RuntimeError("未获取到 DataNode 重定向地址（Location）")

        content = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        headers = {"Content-Type": "application/json; charset=utf-8"}
        step2_resp = requests.put(location, data=content, headers=headers, timeout=effective_timeout)
        step2_resp.raise_for_status()

    def upload_file(
        self,
        local_file_path: str,
        hdfs_path: str,
        overwrite: bool = True,
        timeout: int | None = None,
    ) -> None:
        effective_timeout = timeout if timeout is not None else max(self.timeout, 60)

        step1_url = self._build_url(
            hdfs_path,
            self._with_user(f"op=CREATE&overwrite={'true' if overwrite else 'false'}"),
        )
        step1_resp = requests.put(step1_url, allow_redirects=False, timeout=effective_timeout)
        step1_resp.raise_for_status()

        if step1_resp.status_code == 201:
            return
        if step1_resp.status_code != 307:
            raise RuntimeError(
                f"CREATE 第一步返回异常: status={step1_resp.status_code}, body={step1_resp.text}"
            )

        location = step1_resp.headers.get("Location")
        if not location:
            raise RuntimeError("未获取到 DataNode 重定向地址（Location）")

        with open(local_file_path, "rb") as f:
            headers = {"Content-Type": "application/octet-stream"}
            step2_resp = requests.put(location, data=f, headers=headers, timeout=effective_timeout)
        step2_resp.raise_for_status()


if __name__ == "__main__":
    host = "192.168.157.130"
    port = 9870
    hdfs_dir = "/user/danglong/rice/output"
    hdfs_file = f"{hdfs_dir}/ceshi.py"
    local_file_path = ".\\code\\重构\\main.py"
    payload = {
        "point": "point_1",
        "date": "2025-05-08",
        "output1": "示例输出1",
        "output2": "示例输出2",
        "output3": "示例输出3",
    }

    client = hdfs(namenode_host=host, namenode_port=port, user="root")
    client.mkdirs(hdfs_dir)
    client.upload_file(local_file_path, hdfs_file, overwrite=True)
    print(f"上传完成: {hdfs_file}")
