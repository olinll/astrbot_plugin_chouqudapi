import json
import os
import random
from datetime import datetime
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

@register("chouqudapi", "顾拾柒", "抽取大皮插件 (针对 NapCat QQBot 优化)", "1.0.6")
class ChouQuDaPiPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 获取插件自身的目录，确保数据保存在插件文件夹下的 data 目录中
        self.data_dir = os.path.join(os.path.dirname(__file__), "data")
        self.data_file = os.path.join(self.data_dir, "chouqudapi.json")
        self.default_dapi = [
            "万法之源", "世界之脊", "交汇大厅", "中心城", "枢纽星", 
            "时光废土", "可能海", "明日边境", "命运岔路", "刹那永恒", 
            "静寂虚空", "数据深渊", "永恒炉心", "迷雾之境", "镜世界", 
            "灵魂荒原", "记忆坟场", "回声殿堂", "群星墓园", "众神黄昏"
        ]
        self.data = self._load_data()

    async def _call_api(self, event: AstrMessageEvent, action: str, **params):
        """针对 NapCat/aiocqhttp 优化的 API 调用"""
        bot = event.bot
        
        try:
            # 1. 针对 aiocqhttp (NapCat) 平台
            if event.get_platform_name() == "aiocqhttp":
                if hasattr(bot, "api") and hasattr(bot.api, "call_action"):
                    # 根据报错 "takes 2 positional arguments but 3 were given"
                    # 说明 call_action(self, action, **params) 在当前环境下可能被误解
                    # 我们尝试最直接的属性调用，这在 aiocqhttp 中是支持的：bot.api.action(**params)
                    try:
                        method = getattr(bot.api, action)
                        return await method(**params)
                    except AttributeError:
                        # 如果没有直接的方法，再尝试 call_action
                        # 注意：为了避免 "3 were given"，我们将 params 作为一个 dict 传递
                        # 如果 call_action 定义是 (self, action, params)，这就对了
                        return await bot.api.call_action(action, params)

            # 2. 尝试直接通过 bot 对象调用方法
            if hasattr(bot, action):
                method = getattr(bot, action)
                return await method(**params)

            # 3. 尝试标准 call_api
            return await bot.call_api(action, **params)
        except TypeError as e:
            # 4. 最后的回退
            if "positional arguments but" in str(e) or "takes 2 positional arguments" in str(e):
                try:
                    return await bot.call_api(action, params)
                except:
                    pass
            raise e
        except Exception as e:
            raise e

    def _load_data(self):
        """从本地 JSON 加载数据"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        
        data = {"dapi_pool": self.default_dapi.copy(), "extractions": {}}
        
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    # 如果文件中已经有数据，则合并
                    if "dapi_pool" in loaded_data:
                        # 确保默认的大皮都在池子中
                        for dapi in self.default_dapi:
                            if dapi not in loaded_data["dapi_pool"]:
                                loaded_data["dapi_pool"].append(dapi)
                        data["dapi_pool"] = loaded_data["dapi_pool"]
                    if "extractions" in loaded_data:
                        data["extractions"] = loaded_data["extractions"]
                    return data
            except Exception as e:
                logger.error(f"加载插件数据失败: {e}")
        
        # 如果是新创建的数据，保存一下
        self.data = data
        self._save_data()
        return data

    def _save_data(self):
        """将数据保存到本地 JSON"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"保存插件数据失败: {e}")

    @filter.command("添加大皮")
    async def add_dapi(self, event: AstrMessageEvent, content: str):
        """将内容添加进大皮组"""
        if not content:
            yield event.plain_result("请输入要添加的大皮内容。用法：/添加大皮 <内容>")
            return
        
        # 预处理内容：去除“黄大皮”前缀、“分皮”后缀，以及可能存在的“人类”前缀
        processed_content = content.strip()
        if processed_content.startswith("黄大皮"):
            processed_content = processed_content[len("黄大皮"):]
        if processed_content.endswith("分皮"):
            processed_content = processed_content[:-len("分皮")]
        if processed_content.startswith("人类"):
            processed_content = processed_content[len("人类"):]
            
        if not processed_content:
            yield event.plain_result("处理后的内容为空，请输入有效的大皮内容。")
            return
            
        if processed_content in self.data["dapi_pool"]:
            yield event.plain_result(f"大皮组中已存在：{processed_content}")
            return
            
        self.data["dapi_pool"].append(processed_content)
        self._save_data()
        yield event.plain_result(f"成功添加大皮：{processed_content}")

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
        
        # 记录用户昵称，用于展示
        if "_nicknames" not in self.data["extractions"][group_id]:
            self.data["extractions"][group_id]["_nicknames"] = {}
        self.data["extractions"][group_id]["_nicknames"][user_id] = event.get_sender_name()
        
        self._save_data()

        # 修改群名片
        try:
            await self._call_api(event, "set_group_member_card", 
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
        user_name = event.get_sender_name()
        
        if not group_id:
            yield event.plain_result("此指令仅限群聊使用。")
            return

        user_records = self.data.get("extractions", {}).get(group_id, {}).get(user_id, [])
        if not user_records:
            yield event.plain_result(f"{user_name}，你还没有抽取过大皮。")
            return

        # 按是否为当前以及时间倒序排列，确保当前大皮在最前
        sorted_records = sorted(user_records, key=lambda x: (x["current"], x["time"]), reverse=True)
        
        result_lines = [f"【{user_name}】的大皮记录："]
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

        # 尝试获取群成员列表以获取昵称
        member_nicknames = {}
        try:
            members = await self._call_api(event, "get_group_member_list", group_id=int(group_id))
            for m in members:
                user_id_str = str(m.get("user_id"))
                # 优先使用名片，其次是昵称
                name = m.get("card") or m.get("nickname")
                if name:
                    member_nicknames[user_id_str] = name
        except Exception as e:
            logger.error(f"获取群成员列表失败: {e}")

        result_lines = ["本群大皮成员列表："]
        saved_nicknames = group_data.get("_nicknames", {})
        
        for user_id, records in group_data.items():
            if user_id == "_nicknames": continue # 跳过昵称存储字段
            
            current_dapi = next((r for r in records if r.get("current")), None)
            if current_dapi:
                # 优先级：群成员列表 > 历史记录中的昵称 > 默认展示
                display_name = member_nicknames.get(str(user_id)) or saved_nicknames.get(user_id) or "大皮成员"
                result_lines.append(f"- {display_name}: 黄大皮{current_dapi['name']}分皮")
        
        yield event.plain_result("\n".join(result_lines))
