// 超无穹编剧大师 - 自主决策引擎
module.exports = {
  name: 'chaowuqiong-screenwriting-master',
  version: '1.0.0',
  
  // 决策规则
  decisions: {
    // 格式路由
    routeFormat(userInput) {
      const keywords = {
        ultrashort: ['概念', '超短片', '1分钟', '2分钟', '3分钟', 'what-if', 'how-to-tell'],
        short: ['短片', '5分钟', '8分钟', '10分钟', '叙事短片'],
        feature: ['长片', '电影', '90分钟', '院线'],
        series: ['剧集', '连续剧', '多集', '季播']
      };
      
      for (const [format, kws] of Object.entries(keywords)) {
        if (kws.some(kw => userInput.includes(kw))) return format;
      }
      return null; // 需要询问用户
    },
    
    // 选题路径判断
    detectTopicPath(userInput) {
      if (userInput.match(/关于|探讨|主题|命题/)) return 'theme';
      if (userInput.match(/一个人|角色|人物|性格/)) return 'character';
      if (userInput.match(/空间|地点|环境|建筑/)) return 'space';
      if (userInput.match(/关系|两人|夫妻|对手/)) return 'relationship';
      if (userInput.match(/结合|碰撞|如果|概念/)) return 'concept';
      return 'unknown';
    },
    
    // 工作流步骤控制
    canProceed(currentStep, userConfirmation) {
      return userConfirmation === '通过';
    }
  },
  
  // 自检规则
  selfCheck: {
    // 写作红线检查
    checkRedLines(content) {
      const violations = [];
      if (content.match(/他意识到|她意识到|内心涌起|他觉得|她觉得/)) {
        violations.push('存在心理描写');
      }
      if (content.match(/（其实|（实际上|（暗中/)) {
        violations.push('存在括号暗示');
      }
      return violations;
    },
    
    // 戏剧动作检查
    checkDramaticAction(goal, conflict) {
      return {
        hasGoal: !!goal,
        hasConflict: !!conflict,
        isUrgent: goal && goal.match(/必须|急需|即将|最后/)
      };
    }
  }
};
