// 超无穹导演大师 - 自主决策引擎
module.exports = {
  name: 'chaowuqiong-director-master',
  version: '1.0.0',
  
  // 决策规则
  decisions: {
    // 维度判断
    detectDimensions(scriptContent) {
      const dimensions = [];
      const checks = {
        mood: ['情绪', '氛围', '基调', '温暖', '冷峻', '荒诞'],
        genre: ['惊悚', '恐怖', '犯罪', '科幻', '奇幻', '悬疑'],
        action: ['打斗', '追逐', '战斗', '动作', '武侠'],
        theme: ['爱情', '家庭', '青春', '成长', '亲情'],
        form: ['纪录片', '公路', '歌舞', '动画', '实验'],
        social: ['社会', '历史', '政治', '现实']
      };
      
      for (const [dim, kws] of Object.entries(checks)) {
        if (kws.some(kw => scriptContent.includes(kw))) {
          dimensions.push(dim);
        }
      }
      return dimensions;
    },
    
    // 镜头组类型判断
    determineShotGroupType(purpose) {
      if (purpose.match(/蒙太奇|并列|多个/)) return 'montage';
      if (purpose.match(/递进|层层|升级/)) return 'progressive';
      if (purpose.match(/因果|反应|正反打/)) return 'causal';
      if (purpose.match(/对比|呼应|并置/)) return 'contrast';
      return 'standard';
    },
    
    // 景别推荐
    suggestShotScale(narrativePurpose, emotionalWeight) {
      if (emotionalWeight === '重' && narrativePurpose.match(/情感|内心/)) {
        return '近景/特写';
      }
      if (narrativePurpose.match(/环境|空间|建立/)) {
        return '全景/远景';
      }
      return '中景';
    }
  },
  
  // 自检规则
  selfCheck: {
    // 叙事目的检查
    checkNarrativePurpose(purpose) {
      const issues = [];
      if (!purpose || purpose.length < 10) {
        issues.push('叙事目的过于简短');
      }
      if (purpose.match(/他觉得|她觉得|内心|意识到/)) {
        issues.push('叙事目的包含心理描写');
      }
      return issues;
    },
    
    // 分镜完整性检查
    checkStoryboardCompleteness(storyboard) {
      const requiredColumns = ['镜号', '时长', '摄影角度', '景别', '画面内容', '场景', '声音', '叙事目的'];
      const missing = requiredColumns.filter(col => !storyboard.includes(col));
      return missing;
    }
  }
};
