import json
import os
import random
from datetime import datetime
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

@register("chouqudapi", "顾拾柒", "抽取大皮插件 (针对 NapCat QQBot 优化)", "1.0.0")
class ChouQuDaPiPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.data_dir = os.path.join("data", "plugins")
        self.data_file = os.path.join(self.data_dir, "chouqudapi.json")
        self.data = self._load_data()

    def _load_data(self):
        """从本地 JSON 加载数据"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载插件数据失败: {e}")
        return {"dapi_pool": [], "extractions": {}}

    def _save_data(self):
        """将数据保存到本地 JSON"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"保存插件数据失败: {e}")

    @filter.command("添加大皮组")
    async def add_dapi_group(self, event: AstrMessageEvent, content: str):
        """将内容添加进大皮组"""
        if not content:
            yield event.plain_result("请输入要添加的大皮内容。用法：/添加大皮组 <内容>")
            return
        
        if content in self.data["dapi_pool"]:
            yield event.plain_result(f"大皮组中已存在：{content}")
            return
            
        self.data["dapi_pool"].append(content)
        self._save_data()
        yield event.plain_result(f"成功添加大皮：{content}")

    @filter.command("查看大皮组")
    async def view_dapi_group(self, event: AstrMessageEvent):
        """输出所有大皮"""
        pool = self.data.get("dapi_pool", [])
        if not pool:
            yield event.plain_result("当前大皮组为空。")
            return
        
        result = "当前大皮组：\n" + "\n".join([f"{i+1}. {item}" for i, item in enumerate(pool)])
        yield event.plain_result(result)

    @filter.command("抽取大皮")
    async def draw_dapi(self, event: AstrMessageEvent):
        """根据大皮组平均概率抽取大皮，并修改群名片"""
        pool = self.data.get("dapi_pool", [])
        if not pool:
            yield event.plain_result("当前大皮组为空，请先添加大皮。")
            return

        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("此指令仅限群聊使用。")
            return

        user_id = event.get_sender_id()
        selected_dapi = random.choice(pool)
        new_card = f"黄大皮{selected_dapi}分皮"
        now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 记录数据
        if group_id not in self.data["extractions"]:
            self.data["extractions"][group_id] = {}
        if user_id not in self.data["extractions"][group_id]:
            self.data["extractions"][group_id][user_id] = []
        
        # 将之前的记录标记为非当前
        for record in self.data["extractions"][group_id][user_id]:
            record["current"] = False
            
        self.data["extractions"][group_id][user_id].append({
            "name": selected_dapi,
            "time": now_time,
            "current": True
        })
        self._save_data()

        # 修改群名片
        try:
            await event.bot.call_api("set_group_member_card", 
                                     group_id=int(group_id), 
                                     user_id=int(user_id), 
                                     card=new_card)
            yield event.plain_result(f"恭喜！你抽取到了：{selected_dapi}。群名片已修改为：{new_card}")
        except Exception as e:
            logger.error(f"修改群名片失败: {e}")
            yield event.plain_result(f"恭喜！你抽取到了：{selected_dapi}。但名片修改失败，请检查机器人权限。")

    @filter.command("查看大皮")
    async def view_self_dapi(self, event: AstrMessageEvent):
        """查询发送消息的人历史抽取的大皮信息和现在的大皮信息"""
        group_id = event.get_group_id()
        user_id = event.get_sender_id()
        
        if not group_id:
            yield event.plain_result("此指令仅限群聊使用。")
            return

        user_records = self.data.get("extractions", {}).get(group_id, {}).get(user_id, [])
        if not user_records:
            yield event.plain_result("你还没有抽取过大皮。")
            return

        # 按是否为当前以及时间倒序排列，确保当前大皮在最前
        sorted_records = sorted(user_records, key=lambda x: (x["current"], x["time"]), reverse=True)
        
        result_lines = []
        for i, record in enumerate(sorted_records):
            status = "（当前）" if record["current"] else f"（{record['time']}抽取）"
            result_lines.append(f"{i+1}.黄大皮{record['name']}分皮{status}")
            
        yield event.plain_result("\n".join(result_lines))

    @filter.command("群查看大皮")
    async def view_group_dapi(self, event: AstrMessageEvent):
        """查询当前所有抽取过大皮的人"""
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("此指令仅限群聊使用。")
            return

        group_data = self.data.get("extractions", {}).get(group_id, {})
        if not group_data:
            yield event.plain_result("本群还没有人抽取过大皮。")
            return

        result_lines = ["本群大皮成员列表："]
        for user_id, records in group_data.items():
            current_dapi = next((r for r in records if r.get("current")), None)
            if current_dapi:
                # 这里尝试获取用户名，如果获取不到则显示 ID
                result_lines.append(f"- 用户 {user_id}: 黄大皮{current_dapi['name']}分皮")
        
        yield event.plain_result("\n".join(result_lines))
